import httpx
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from .base_adapter import BasePOSAdapter
from ..schemas.pos_schemas import SyncResponse


logger = logging.getLogger(__name__)


class SquareRateLimiter:
    """Rate limiter for Square API requests"""
    
    def __init__(self, requests_per_minute: int = 500):
        self.requests_per_minute = requests_per_minute
        self.requests = []
        self.lock = asyncio.Lock()
    
    async def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        async with self.lock:
            now = datetime.utcnow()
            # Remove requests older than 1 minute
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < timedelta(minutes=1)]
            
            if len(self.requests) >= self.requests_per_minute:
                # Calculate wait time until oldest request is over 1 minute old
                oldest_request = min(self.requests)
                wait_until = oldest_request + timedelta(minutes=1)
                wait_seconds = (wait_until - now).total_seconds()
                
                if wait_seconds > 0:
                    logger.info(f"Rate limit reached, waiting {wait_seconds:.2f} seconds")
                    await asyncio.sleep(wait_seconds)
            
            # Record this request
            self.requests.append(now)


class SquareAdapter(BasePOSAdapter):
    def __init__(self, credentials: Dict[str, Any]):
        super().__init__(credentials)
        self.base_url = "https://connect.squareup.com/v2"
        self.headers = {
            "Authorization": f"Bearer {credentials.get('access_token')}",
            "Content-Type": "application/json"
        }
        
        # Rate limiting
        rate_limit = credentials.get('rate_limit_requests', 500)
        self.rate_limiter = SquareRateLimiter(rate_limit)
        
        # Request configuration
        self.timeout = credentials.get('timeout_seconds', 30)
        self.max_retries = credentials.get('max_retries', 3)
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Make HTTP request with rate limiting, retries, and error handling"""
        
        for attempt in range(self.max_retries + 1):
            try:
                # Apply rate limiting
                await self.rate_limiter.wait_if_needed()
                
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method=method,
                        url=f"{self.base_url}{endpoint}",
                        headers=self.headers,
                        timeout=self.timeout,
                        **kwargs
                    )
                    
                    # Handle rate limiting from Square
                    if response.status_code == 429:
                        retry_after = response.headers.get('Retry-After', 60)
                        wait_time = int(retry_after)
                        logger.warning(f"Square rate limit hit, waiting {wait_time} seconds")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    # Handle other HTTP errors
                    if response.status_code >= 400:
                        error_details = self._parse_error_response(response)
                        logger.error(f"Square API error {response.status_code}: {error_details}")
                        
                        # Don't retry client errors (4xx) except rate limiting
                        if response.status_code >= 400 and response.status_code < 500:
                            if response.status_code != 429:  # Already handled above
                                response.raise_for_status()
                    
                    response.raise_for_status()
                    return response
                    
            except httpx.TimeoutException as e:
                logger.warning(f"Square API timeout (attempt {attempt + 1}/{self.max_retries + 1}): {str(e)}")
                if attempt == self.max_retries:
                    raise Exception(f"Square API timeout after {self.max_retries + 1} attempts")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            except httpx.ConnectError as e:
                logger.warning(f"Square API connection error (attempt {attempt + 1}/{self.max_retries + 1}): {str(e)}")
                if attempt == self.max_retries:
                    raise Exception(f"Square API connection failed after {self.max_retries + 1} attempts")
                await asyncio.sleep(2 ** attempt)
                
            except httpx.HTTPStatusError as e:
                # For HTTP errors, only retry 5xx server errors
                if e.response.status_code >= 500:
                    logger.warning(f"Square API server error (attempt {attempt + 1}/{self.max_retries + 1}): {e.response.status_code}")
                    if attempt == self.max_retries:
                        raise Exception(f"Square API server error after {self.max_retries + 1} attempts: {e.response.status_code}")
                    await asyncio.sleep(2 ** attempt)
                else:
                    # Don't retry client errors
                    raise e
            
            except Exception as e:
                logger.error(f"Unexpected error making Square API request: {str(e)}")
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(2 ** attempt)
        
        raise Exception("Max retries exceeded")
    
    def _parse_error_response(self, response: httpx.Response) -> str:
        """Parse Square API error response for detailed error information"""
        try:
            error_data = response.json()
            
            if "errors" in error_data:
                errors = []
                for error in error_data["errors"]:
                    error_detail = error.get("detail", "Unknown error")
                    error_code = error.get("code", "UNKNOWN")
                    error_category = error.get("category", "UNKNOWN")
                    errors.append(f"{error_category}.{error_code}: {error_detail}")
                return "; ".join(errors)
            
            return error_data.get("message", f"HTTP {response.status_code}")
            
        except Exception:
            return f"HTTP {response.status_code}: {response.text[:200]}"
    
    def _log_request_details(self, method: str, endpoint: str, **kwargs):
        """Log request details for debugging"""
        logger.debug(f"Square API {method} {endpoint}")
        if "json" in kwargs:
            logger.debug(f"Request body: {kwargs['json']}")
    
    async def _handle_batch_operation(self, operation_name: str, items: List[Dict], 
                                    batch_size: int = 50) -> List[Dict]:
        """Handle batch operations with proper error handling and logging"""
        results = []
        failed_items = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_number = (i // batch_size) + 1
            total_batches = (len(items) + batch_size - 1) // batch_size
            
            logger.info(f"Processing {operation_name} batch {batch_number}/{total_batches} ({len(batch)} items)")
            
            try:
                # Process batch (implementation depends on specific operation)
                batch_results = await self._process_batch(operation_name, batch)
                results.extend(batch_results)
                
            except Exception as e:
                logger.error(f"Batch {batch_number} failed: {str(e)}")
                failed_items.extend(batch)
        
        if failed_items:
            logger.warning(f"{len(failed_items)} items failed during {operation_name}")
        
        return results
    
    async def _process_batch(self, operation_name: str, batch: List[Dict]) -> List[Dict]:
        """Process a single batch - to be implemented by specific operations"""
        # Placeholder - specific implementations would override this
        return batch

    async def push_order(self, order_data: Dict[str, Any]) -> SyncResponse:
        transformed_data = self.transform_order_data(order_data)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/orders",
                    json=transformed_data,
                    headers=self.headers,
                    timeout=30.0,
                )
                response.raise_for_status()
                return SyncResponse(
                    success=True, message="Order pushed successfully to Square"
                )
            except httpx.HTTPError as e:
                return SyncResponse(
                    success=False, message=f"Square API error: {str(e)}"
                )

    async def test_connection(self) -> bool:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/locations",
                    headers=self.headers,
                    timeout=10.0
                )
                return response.status_code == 200
            except Exception:
                return False

    def transform_order_data(self, order: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "order": {
                "location_id": self.credentials.get("location_id"),
                "line_items": [
                    {
                        "name": f"Menu Item {item['menu_item_id']}",
                        "quantity": str(item["quantity"]),
                        "base_price_money": {
                            "amount": int(item["price"] * 100),
                            "currency": "USD"
                        },
                        "note": item.get("notes", "")
                    }
                    for item in order.get("items", [])
                ],
                "metadata": {
                    "aura_order_id": str(order["id"]),
                    "table_no": str(order.get("table_no", "")),
                    "staff_id": str(order["staff_id"])
                }
            }
        }

    async def get_vendor_orders(
        self, since_timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            try:
                params = {}
                if since_timestamp:
                    params["updated_at"] = f">{since_timestamp.isoformat()}"

                response = await client.get(
                    f"{self.base_url}/orders/search",
                    headers=self.headers,
                    params=params,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError:
                return {"orders": []}

    # Menu synchronization methods implementation for Square
    async def get_menu_categories(self, since_timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get menu categories from Square"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/catalog/list",
                    headers=self.headers,
                    params={"types": "CATEGORY"},
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                
                categories = []
                for item in data.get("objects", []):
                    if item.get("type") == "CATEGORY":
                        categories.append(self.transform_category_from_pos(item))
                
                return categories
            except httpx.HTTPError:
                return []

    async def get_menu_items(self, since_timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get menu items from Square"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/catalog/list",
                    headers=self.headers,
                    params={"types": "ITEM"},
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                
                items = []
                for item in data.get("objects", []):
                    if item.get("type") == "ITEM":
                        items.append(self.transform_item_from_pos(item))
                
                return items
            except httpx.HTTPError:
                return []

    async def get_modifier_groups(self, since_timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get modifier groups from Square"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/catalog/list",
                    headers=self.headers,
                    params={"types": "MODIFIER_LIST"},
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                
                modifier_groups = []
                for item in data.get("objects", []):
                    if item.get("type") == "MODIFIER_LIST":
                        modifier_groups.append(self.transform_modifier_group_from_pos(item))
                
                return modifier_groups
            except httpx.HTTPError:
                return []

    async def get_modifiers(self, modifier_group_id: str) -> List[Dict[str, Any]]:
        """Get modifiers for a specific modifier group from Square"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/catalog/object/{modifier_group_id}",
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                
                modifiers = []
                modifier_list_data = data.get("object", {}).get("modifier_list_data", {})
                for modifier in modifier_list_data.get("modifiers", []):
                    modifiers.append(self.transform_modifier_from_pos(modifier))
                
                return modifiers
            except httpx.HTTPError:
                return []

    async def create_menu_category(self, category_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new menu category in Square"""
        square_category = self.transform_category_to_pos(category_data)
        
        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    "idempotency_key": f"cat_{category_data.get('id', 'new')}_{datetime.utcnow().timestamp()}",
                    "object": {
                        "type": "CATEGORY",
                        "id": f"#category_{category_data.get('id', 'new')}",
                        "category_data": {
                            "name": square_category["name"]
                        }
                    }
                }
                
                response = await client.post(
                    f"{self.base_url}/catalog/object",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json().get("catalog_object", {})
            except httpx.HTTPError as e:
                raise Exception(f"Failed to create category in Square: {str(e)}")

    async def update_menu_category(self, category_id: str, category_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing menu category in Square"""
        square_category = self.transform_category_to_pos(category_data)
        
        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    "idempotency_key": f"cat_update_{category_id}_{datetime.utcnow().timestamp()}",
                    "object": {
                        "type": "CATEGORY",
                        "id": category_id,
                        "category_data": {
                            "name": square_category["name"]
                        }
                    }
                }
                
                response = await client.post(
                    f"{self.base_url}/catalog/object",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json().get("catalog_object", {})
            except httpx.HTTPError as e:
                raise Exception(f"Failed to update category in Square: {str(e)}")

    async def delete_menu_category(self, category_id: str) -> bool:
        """Delete a menu category from Square"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self.base_url}/catalog/object/{category_id}",
                    headers=self.headers,
                    timeout=30.0
                )
                return response.status_code == 200
            except httpx.HTTPError:
                return False

    async def create_menu_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new menu item in Square"""
        square_item = self.transform_item_to_pos(item_data)
        
        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    "idempotency_key": f"item_{item_data.get('id', 'new')}_{datetime.utcnow().timestamp()}",
                    "object": {
                        "type": "ITEM",
                        "id": f"#item_{item_data.get('id', 'new')}",
                        "item_data": {
                            "name": square_item["name"],
                            "description": square_item.get("description", ""),
                            "category_id": square_item.get("category_id"),
                            "variations": [
                                {
                                    "type": "ITEM_VARIATION",
                                    "id": f"#variation_{item_data.get('id', 'new')}",
                                    "item_variation_data": {
                                        "item_id": f"#item_{item_data.get('id', 'new')}",
                                        "name": "Regular",
                                        "pricing_type": "FIXED_PRICING",
                                        "price_money": {
                                            "amount": int(square_item["price"] * 100),
                                            "currency": "USD"
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
                
                response = await client.post(
                    f"{self.base_url}/catalog/object",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json().get("catalog_object", {})
            except httpx.HTTPError as e:
                raise Exception(f"Failed to create item in Square: {str(e)}")

    async def update_menu_item(self, item_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing menu item in Square"""
        square_item = self.transform_item_to_pos(item_data)
        
        async with httpx.AsyncClient() as client:
            try:
                # First get the existing item to preserve variation IDs
                existing_response = await client.get(
                    f"{self.base_url}/catalog/object/{item_id}",
                    headers=self.headers,
                    timeout=30.0
                )
                existing_data = existing_response.json().get("object", {})
                
                payload = {
                    "idempotency_key": f"item_update_{item_id}_{datetime.utcnow().timestamp()}",
                    "object": {
                        "type": "ITEM",
                        "id": item_id,
                        "version": existing_data.get("version"),
                        "item_data": {
                            "name": square_item["name"],
                            "description": square_item.get("description", ""),
                            "category_id": square_item.get("category_id")
                        }
                    }
                }
                
                response = await client.post(
                    f"{self.base_url}/catalog/object",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json().get("catalog_object", {})
            except httpx.HTTPError as e:
                raise Exception(f"Failed to update item in Square: {str(e)}")

    async def delete_menu_item(self, item_id: str) -> bool:
        """Delete a menu item from Square"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self.base_url}/catalog/object/{item_id}",
                    headers=self.headers,
                    timeout=30.0
                )
                return response.status_code == 200
            except httpx.HTTPError:
                return False

    async def create_modifier_group(self, modifier_group_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new modifier group in Square"""
        square_modifier_group = self.transform_modifier_group_to_pos(modifier_group_data)
        
        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    "idempotency_key": f"modgroup_{modifier_group_data.get('id', 'new')}_{datetime.utcnow().timestamp()}",
                    "object": {
                        "type": "MODIFIER_LIST",
                        "id": f"#modifier_list_{modifier_group_data.get('id', 'new')}",
                        "modifier_list_data": {
                            "name": square_modifier_group["name"],
                            "selection_type": "SINGLE" if square_modifier_group["selection_type"] == "single" else "MULTIPLE",
                            "modifiers": []
                        }
                    }
                }
                
                response = await client.post(
                    f"{self.base_url}/catalog/object",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json().get("catalog_object", {})
            except httpx.HTTPError as e:
                raise Exception(f"Failed to create modifier group in Square: {str(e)}")

    async def update_modifier_group(self, modifier_group_id: str, modifier_group_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing modifier group in Square"""
        square_modifier_group = self.transform_modifier_group_to_pos(modifier_group_data)
        
        async with httpx.AsyncClient() as client:
            try:
                # Get existing modifier group to preserve version and modifiers
                existing_response = await client.get(
                    f"{self.base_url}/catalog/object/{modifier_group_id}",
                    headers=self.headers,
                    timeout=30.0
                )
                existing_data = existing_response.json().get("object", {})
                existing_modifier_list = existing_data.get("modifier_list_data", {})
                
                payload = {
                    "idempotency_key": f"modgroup_update_{modifier_group_id}_{datetime.utcnow().timestamp()}",
                    "object": {
                        "type": "MODIFIER_LIST",
                        "id": modifier_group_id,
                        "version": existing_data.get("version"),
                        "modifier_list_data": {
                            "name": square_modifier_group["name"],
                            "selection_type": "SINGLE" if square_modifier_group["selection_type"] == "single" else "MULTIPLE",
                            "modifiers": existing_modifier_list.get("modifiers", [])
                        }
                    }
                }
                
                response = await client.post(
                    f"{self.base_url}/catalog/object",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json().get("catalog_object", {})
            except httpx.HTTPError as e:
                raise Exception(f"Failed to update modifier group in Square: {str(e)}")

    async def delete_modifier_group(self, modifier_group_id: str) -> bool:
        """Delete a modifier group from Square"""
        return await self.delete_menu_category(modifier_group_id)  # Same API endpoint

    async def create_modifier(self, modifier_group_id: str, modifier_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new modifier in Square modifier group"""
        square_modifier = self.transform_modifier_to_pos(modifier_data)
        
        async with httpx.AsyncClient() as client:
            try:
                # Get existing modifier group
                existing_response = await client.get(
                    f"{self.base_url}/catalog/object/{modifier_group_id}",
                    headers=self.headers,
                    timeout=30.0
                )
                existing_data = existing_response.json().get("object", {})
                existing_modifier_list = existing_data.get("modifier_list_data", {})
                existing_modifiers = existing_modifier_list.get("modifiers", [])
                
                # Add new modifier
                new_modifier = {
                    "type": "MODIFIER",
                    "id": f"#modifier_{modifier_data.get('id', 'new')}",
                    "modifier_data": {
                        "name": square_modifier["name"],
                        "price_money": {
                            "amount": int(square_modifier["price_adjustment"] * 100),
                            "currency": "USD"
                        }
                    }
                }
                existing_modifiers.append(new_modifier)
                
                payload = {
                    "idempotency_key": f"modifier_{modifier_data.get('id', 'new')}_{datetime.utcnow().timestamp()}",
                    "object": {
                        "type": "MODIFIER_LIST",
                        "id": modifier_group_id,
                        "version": existing_data.get("version"),
                        "modifier_list_data": {
                            **existing_modifier_list,
                            "modifiers": existing_modifiers
                        }
                    }
                }
                
                response = await client.post(
                    f"{self.base_url}/catalog/object",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                return new_modifier
            except httpx.HTTPError as e:
                raise Exception(f"Failed to create modifier in Square: {str(e)}")

    async def update_modifier(self, modifier_id: str, modifier_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing modifier in Square"""
        # Square modifiers are part of modifier lists, so we need to update the whole list
        # This is a simplified implementation - in practice, you'd need to find the parent list
        square_modifier = self.transform_modifier_to_pos(modifier_data)
        return {
            "id": modifier_id,
            "modifier_data": {
                "name": square_modifier["name"],
                "price_money": {
                    "amount": int(square_modifier["price_adjustment"] * 100),
                    "currency": "USD"
                }
            }
        }

    async def delete_modifier(self, modifier_id: str) -> bool:
        """Delete a modifier from Square"""
        # Similar to update, this would require updating the parent modifier list
        # Simplified implementation
        return True

    def transform_category_from_pos(self, pos_category_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform Square category format to AuraConnect format"""
        category_data = pos_category_data.get("category_data", {})
        return {
            "id": pos_category_data.get("id"),
            "name": category_data.get("name", ""),
            "description": "",
            "display_order": 0,
            "is_active": not pos_category_data.get("is_deleted", False),
            "pos_specific_data": pos_category_data,
            "updated_at": pos_category_data.get("updated_at")
        }

    def transform_item_from_pos(self, pos_item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform Square item format to AuraConnect format"""
        item_data = pos_item_data.get("item_data", {})
        variations = item_data.get("variations", [])
        
        # Get price from first variation
        price = 0.0
        if variations:
            variation_data = variations[0].get("item_variation_data", {})
            price_money = variation_data.get("price_money", {})
            price = price_money.get("amount", 0) / 100.0  # Convert from cents
        
        return {
            "id": pos_item_data.get("id"),
            "name": item_data.get("name", ""),
            "description": item_data.get("description", ""),
            "price": price,
            "category_id": item_data.get("category_id"),
            "sku": "",
            "is_active": not pos_item_data.get("is_deleted", False),
            "is_available": True,
            "pos_specific_data": pos_item_data,
            "updated_at": pos_item_data.get("updated_at")
        }

    def transform_modifier_group_from_pos(self, pos_modifier_group_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform Square modifier group format to AuraConnect format"""
        modifier_list_data = pos_modifier_group_data.get("modifier_list_data", {})
        selection_type = modifier_list_data.get("selection_type", "SINGLE")
        
        return {
            "id": pos_modifier_group_data.get("id"),
            "name": modifier_list_data.get("name", ""),
            "description": "",
            "selection_type": "single" if selection_type == "SINGLE" else "multiple",
            "min_selections": 0,
            "max_selections": 1 if selection_type == "SINGLE" else None,
            "is_required": False,
            "is_active": not pos_modifier_group_data.get("is_deleted", False),
            "pos_specific_data": pos_modifier_group_data,
            "updated_at": pos_modifier_group_data.get("updated_at")
        }

    def transform_modifier_from_pos(self, pos_modifier_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform Square modifier format to AuraConnect format"""
        modifier_data = pos_modifier_data.get("modifier_data", {})
        price_money = modifier_data.get("price_money", {})
        price_adjustment = price_money.get("amount", 0) / 100.0  # Convert from cents
        
        return {
            "id": pos_modifier_data.get("id"),
            "name": modifier_data.get("name", ""),
            "description": "",
            "price_adjustment": price_adjustment,
            "price_type": "fixed",
            "is_active": not pos_modifier_data.get("is_deleted", False),
            "is_available": True,
            "pos_specific_data": pos_modifier_data,
            "updated_at": pos_modifier_data.get("updated_at")
        }
