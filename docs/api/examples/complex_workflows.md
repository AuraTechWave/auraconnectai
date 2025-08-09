# Complex API Workflow Examples

This document provides detailed examples of complex workflows using the AuraConnect API, demonstrating real-world integration scenarios.

## Order Processing Workflow

### Complete Order Flow
This example shows the complete order flow from creation to completion, including payment processing and inventory updates.

```python
import requests
import time
from typing import Dict, List

class AuraConnectOrderFlow:
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def create_order(self, customer_id: int, items: List[Dict]) -> Dict:
        """Create a new order with validation"""
        # Step 1: Validate item availability
        for item in items:
            availability = self._check_availability(item["menu_item_id"], item["quantity"])
            if not availability["available"]:
                raise Exception(f"Item {item['menu_item_id']} not available")
        
        # Step 2: Create order
        order_data = {
            "customer_id": customer_id,
            "items": items,
            "type": "dine_in",
            "table_number": "5"
        }
        
        response = requests.post(
            f"{self.base_url}/api/v1/orders",
            json=order_data,
            headers=self.headers
        )
        response.raise_for_status()
        order = response.json()
        
        # Step 3: Apply promotions
        order = self._apply_promotions(order["id"])
        
        return order
    
    def _check_availability(self, menu_item_id: int, quantity: int) -> Dict:
        """Check item availability through inventory"""
        response = requests.get(
            f"{self.base_url}/api/v1/menu/{menu_item_id}/availability",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def _apply_promotions(self, order_id: int) -> Dict:
        """Apply available promotions to order"""
        response = requests.post(
            f"{self.base_url}/api/v1/orders/{order_id}/apply-promotions",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def process_payment(self, order_id: int, payment_method: Dict) -> Dict:
        """Process payment with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/api/v1/orders/{order_id}/payment",
                    json=payment_method,
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
    
    def complete_order_flow(self, customer_id: int, items: List[Dict], payment_method: Dict):
        """Complete end-to-end order flow"""
        try:
            # Create order
            print("Creating order...")
            order = self.create_order(customer_id, items)
            print(f"Order created: {order['id']}")
            
            # Process payment
            print("Processing payment...")
            payment = self.process_payment(order["id"], payment_method)
            print(f"Payment successful: {payment['transaction_id']}")
            
            # Update order status
            print("Confirming order...")
            response = requests.patch(
                f"{self.base_url}/api/v1/orders/{order['id']}",
                json={"status": "confirmed"},
                headers=self.headers
            )
            response.raise_for_status()
            
            # Send to kitchen
            print("Sending to kitchen...")
            response = requests.post(
                f"{self.base_url}/api/v1/orders/{order['id']}/send-to-kitchen",
                headers=self.headers
            )
            response.raise_for_status()
            
            return {
                "success": True,
                "order_id": order["id"],
                "payment_id": payment["transaction_id"]
            }
            
        except Exception as e:
            print(f"Order flow failed: {str(e)}")
            # Rollback logic here
            raise

# Usage example
client = AuraConnectOrderFlow(
    api_key="your_api_key",
    base_url="https://api.auraconnect.com"
)

result = client.complete_order_flow(
    customer_id=123,
    items=[
        {"menu_item_id": 10, "quantity": 2, "modifiers": []},
        {"menu_item_id": 15, "quantity": 1, "modifiers": [{"id": 5, "quantity": 1}]}
    ],
    payment_method={
        "type": "card",
        "token": "tok_visa_4242"
    }
)
```

## Multi-Restaurant Order Synchronization

### Syncing Orders Across Multiple Locations
This example demonstrates how to handle orders across multiple restaurant locations with proper synchronization.

```javascript
class MultiRestaurantOrderSync {
  constructor(apiKey, baseUrl) {
    this.apiKey = apiKey;
    this.baseUrl = baseUrl;
    this.headers = {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json'
    };
  }

  async syncOrdersAcrossLocations(chainId, startDate, endDate) {
    try {
      // Step 1: Get all restaurant locations
      const restaurants = await this.getRestaurantLocations(chainId);
      console.log(`Found ${restaurants.length} locations`);

      // Step 2: Fetch orders from each location in parallel
      const orderPromises = restaurants.map(restaurant => 
        this.fetchRestaurantOrders(restaurant.id, startDate, endDate)
      );
      
      const ordersByLocation = await Promise.all(orderPromises);
      
      // Step 3: Aggregate data
      const aggregatedData = this.aggregateOrderData(ordersByLocation, restaurants);
      
      // Step 4: Sync with central system
      const syncResult = await this.syncToCentralSystem(chainId, aggregatedData);
      
      // Step 5: Update local caches
      await this.updateLocalCaches(restaurants, syncResult);
      
      return {
        success: true,
        locations_synced: restaurants.length,
        total_orders: aggregatedData.total_orders,
        sync_id: syncResult.sync_id
      };
      
    } catch (error) {
      console.error('Sync failed:', error);
      await this.handleSyncFailure(chainId, error);
      throw error;
    }
  }

  async getRestaurantLocations(chainId) {
    const response = await fetch(
      `${this.baseUrl}/api/v1/chains/${chainId}/restaurants`,
      { headers: this.headers }
    );
    
    if (!response.ok) throw new Error(`Failed to fetch locations: ${response.status}`);
    return response.json();
  }

  async fetchRestaurantOrders(restaurantId, startDate, endDate) {
    const params = new URLSearchParams({
      start_date: startDate,
      end_date: endDate,
      include_items: true,
      include_payments: true
    });
    
    const response = await fetch(
      `${this.baseUrl}/api/v1/restaurants/${restaurantId}/orders?${params}`,
      { headers: this.headers }
    );
    
    if (!response.ok) throw new Error(`Failed to fetch orders for restaurant ${restaurantId}`);
    return response.json();
  }

  aggregateOrderData(ordersByLocation, restaurants) {
    const aggregated = {
      total_orders: 0,
      total_revenue: 0,
      by_location: {},
      by_hour: {},
      top_items: {}
    };

    ordersByLocation.forEach((orders, index) => {
      const restaurant = restaurants[index];
      
      aggregated.by_location[restaurant.id] = {
        name: restaurant.name,
        order_count: orders.length,
        revenue: orders.reduce((sum, order) => sum + order.total_amount, 0)
      };
      
      aggregated.total_orders += orders.length;
      aggregated.total_revenue += aggregated.by_location[restaurant.id].revenue;
      
      // Aggregate by hour and items
      orders.forEach(order => {
        const hour = new Date(order.created_at).getHours();
        aggregated.by_hour[hour] = (aggregated.by_hour[hour] || 0) + 1;
        
        order.items.forEach(item => {
          const key = item.menu_item_id;
          aggregated.top_items[key] = (aggregated.top_items[key] || 0) + item.quantity;
        });
      });
    });

    return aggregated;
  }

  async syncToCentralSystem(chainId, aggregatedData) {
    const response = await fetch(
      `${this.baseUrl}/api/v1/chains/${chainId}/sync`,
      {
        method: 'POST',
        headers: this.headers,
        body: JSON.stringify({
          type: 'order_aggregation',
          data: aggregatedData,
          timestamp: new Date().toISOString()
        })
      }
    );
    
    if (!response.ok) throw new Error('Central sync failed');
    return response.json();
  }

  async updateLocalCaches(restaurants, syncResult) {
    const cacheUpdates = restaurants.map(restaurant => 
      fetch(`${this.baseUrl}/api/v1/restaurants/${restaurant.id}/cache/update`, {
        method: 'POST',
        headers: this.headers,
        body: JSON.stringify({
          sync_id: syncResult.sync_id,
          last_sync: new Date().toISOString()
        })
      })
    );
    
    await Promise.all(cacheUpdates);
  }

  async handleSyncFailure(chainId, error) {
    // Log failure for monitoring
    await fetch(`${this.baseUrl}/api/v1/chains/${chainId}/sync/failures`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        error: error.message,
        stack: error.stack,
        timestamp: new Date().toISOString()
      })
    });
  }
}

// Usage
const syncClient = new MultiRestaurantOrderSync(
  'your_api_key',
  'https://api.auraconnect.com'
);

syncClient.syncOrdersAcrossLocations(
  'chain_123',
  '2025-08-01',
  '2025-08-08'
).then(result => {
  console.log('Sync completed:', result);
}).catch(error => {
  console.error('Sync failed:', error);
});
```

## Advanced Inventory Management with Recipe Integration

### Auto-Reordering Based on Recipe Requirements
This example shows how to implement intelligent inventory management that considers recipe requirements and automatically creates purchase orders.

```python
import asyncio
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime, timedelta

class AdvancedInventoryManager:
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
    async def analyze_and_reorder(self, restaurant_id: int, forecast_days: int = 7):
        """Analyze inventory needs and create purchase orders"""
        async with aiohttp.ClientSession() as session:
            # Step 1: Get current inventory levels
            inventory = await self._get_current_inventory(session, restaurant_id)
            
            # Step 2: Get sales forecast
            forecast = await self._get_sales_forecast(session, restaurant_id, forecast_days)
            
            # Step 3: Calculate required inventory based on recipes
            requirements = await self._calculate_requirements(
                session, restaurant_id, forecast, inventory
            )
            
            # Step 4: Generate purchase orders
            purchase_orders = await self._generate_purchase_orders(
                session, restaurant_id, requirements
            )
            
            # Step 5: Submit orders with approval workflow
            results = await self._submit_purchase_orders(session, purchase_orders)
            
            return {
                "analysis_date": datetime.now().isoformat(),
                "forecast_days": forecast_days,
                "items_analyzed": len(inventory),
                "purchase_orders_created": len(results),
                "total_cost": sum(po["total_cost"] for po in purchase_orders),
                "orders": results
            }
    
    async def _get_current_inventory(self, session, restaurant_id: int) -> Dict:
        """Fetch current inventory levels with alerts"""
        async with session.get(
            f"{self.base_url}/api/v1/restaurants/{restaurant_id}/inventory",
            headers=self.headers,
            params={"include_alerts": "true"}
        ) as response:
            return await response.json()
    
    async def _get_sales_forecast(self, session, restaurant_id: int, days: int) -> Dict:
        """Get AI-powered sales forecast"""
        end_date = datetime.now() + timedelta(days=days)
        
        async with session.post(
            f"{self.base_url}/api/v1/restaurants/{restaurant_id}/forecast",
            headers=self.headers,
            json={
                "start_date": datetime.now().isoformat(),
                "end_date": end_date.isoformat(),
                "include_seasonality": True,
                "include_events": True
            }
        ) as response:
            return await response.json()
    
    async def _calculate_requirements(self, session, restaurant_id: int, 
                                    forecast: Dict, inventory: Dict) -> List[Dict]:
        """Calculate ingredient requirements based on forecasted sales"""
        requirements = []
        
        # Get all active recipes
        async with session.get(
            f"{self.base_url}/api/v1/restaurants/{restaurant_id}/recipes",
            headers=self.headers,
            params={"active_only": "true"}
        ) as response:
            recipes = await response.json()
        
        # Calculate requirements for each forecasted item
        for item_forecast in forecast["items"]:
            menu_item_id = item_forecast["menu_item_id"]
            forecasted_quantity = item_forecast["quantity"]
            
            # Find recipe for this menu item
            recipe = next((r for r in recipes if r["menu_item_id"] == menu_item_id), None)
            if not recipe:
                continue
            
            # Calculate ingredient needs
            for ingredient in recipe["ingredients"]:
                required_quantity = ingredient["quantity"] * forecasted_quantity
                current_stock = next(
                    (inv["quantity"] for inv in inventory["items"] 
                     if inv["ingredient_id"] == ingredient["ingredient_id"]), 
                    0
                )
                
                if required_quantity > current_stock:
                    requirements.append({
                        "ingredient_id": ingredient["ingredient_id"],
                        "ingredient_name": ingredient["name"],
                        "required_quantity": required_quantity,
                        "current_stock": current_stock,
                        "shortage": required_quantity - current_stock,
                        "unit": ingredient["unit"],
                        "for_menu_items": [menu_item_id]
                    })
        
        # Consolidate requirements by ingredient
        consolidated = {}
        for req in requirements:
            key = req["ingredient_id"]
            if key in consolidated:
                consolidated[key]["shortage"] += req["shortage"]
                consolidated[key]["for_menu_items"].extend(req["for_menu_items"])
            else:
                consolidated[key] = req
        
        return list(consolidated.values())
    
    async def _generate_purchase_orders(self, session, restaurant_id: int, 
                                      requirements: List[Dict]) -> List[Dict]:
        """Generate optimized purchase orders"""
        # Get supplier information
        async with session.get(
            f"{self.base_url}/api/v1/restaurants/{restaurant_id}/suppliers",
            headers=self.headers
        ) as response:
            suppliers = await response.json()
        
        # Group requirements by preferred supplier
        orders_by_supplier = {}
        
        for req in requirements:
            # Find best supplier for this ingredient
            supplier = await self._find_best_supplier(
                session, restaurant_id, req["ingredient_id"], suppliers
            )
            
            if supplier["id"] not in orders_by_supplier:
                orders_by_supplier[supplier["id"]] = {
                    "supplier_id": supplier["id"],
                    "supplier_name": supplier["name"],
                    "items": [],
                    "total_cost": 0
                }
            
            # Add buffer for safety stock (20%)
            order_quantity = req["shortage"] * 1.2
            
            # Get pricing
            price = await self._get_ingredient_price(
                session, supplier["id"], req["ingredient_id"], order_quantity
            )
            
            orders_by_supplier[supplier["id"]]["items"].append({
                "ingredient_id": req["ingredient_id"],
                "ingredient_name": req["ingredient_name"],
                "quantity": order_quantity,
                "unit": req["unit"],
                "unit_price": price["unit_price"],
                "total_price": price["total_price"],
                "for_menu_items": req["for_menu_items"]
            })
            
            orders_by_supplier[supplier["id"]]["total_cost"] += price["total_price"]
        
        return list(orders_by_supplier.values())
    
    async def _find_best_supplier(self, session, restaurant_id: int, 
                                 ingredient_id: int, suppliers: List[Dict]) -> Dict:
        """Find best supplier based on price, reliability, and delivery time"""
        supplier_scores = []
        
        for supplier in suppliers:
            # Check if supplier carries this ingredient
            async with session.get(
                f"{self.base_url}/api/v1/suppliers/{supplier['id']}/ingredients/{ingredient_id}",
                headers=self.headers
            ) as response:
                if response.status != 200:
                    continue
                
                data = await response.json()
                
                # Calculate score based on multiple factors
                score = (
                    data["reliability_score"] * 0.4 +
                    (100 - data["price_index"]) * 0.3 +
                    (100 - data["delivery_days"] * 10) * 0.3
                )
                
                supplier_scores.append({
                    "supplier": supplier,
                    "score": score
                })
        
        # Return supplier with highest score
        return max(supplier_scores, key=lambda x: x["score"])["supplier"]
    
    async def _get_ingredient_price(self, session, supplier_id: int, 
                                   ingredient_id: int, quantity: float) -> Dict:
        """Get pricing with bulk discounts"""
        async with session.post(
            f"{self.base_url}/api/v1/suppliers/{supplier_id}/pricing",
            headers=self.headers,
            json={
                "ingredient_id": ingredient_id,
                "quantity": quantity
            }
        ) as response:
            return await response.json()
    
    async def _submit_purchase_orders(self, session, purchase_orders: List[Dict]) -> List[Dict]:
        """Submit purchase orders with approval workflow"""
        results = []
        
        for po in purchase_orders:
            # Check if approval needed based on total cost
            needs_approval = po["total_cost"] > 1000
            
            async with session.post(
                f"{self.base_url}/api/v1/purchase-orders",
                headers=self.headers,
                json={
                    "supplier_id": po["supplier_id"],
                    "items": po["items"],
                    "total_cost": po["total_cost"],
                    "auto_approve": not needs_approval,
                    "notes": "Auto-generated based on forecast"
                }
            ) as response:
                result = await response.json()
                results.append(result)
                
                if needs_approval:
                    # Send notification for approval
                    await self._send_approval_notification(session, result)
        
        return results
    
    async def _send_approval_notification(self, session, purchase_order: Dict):
        """Send notification to manager for approval"""
        await session.post(
            f"{self.base_url}/api/v1/notifications",
            headers=self.headers,
            json={
                "type": "purchase_order_approval",
                "priority": "high",
                "data": {
                    "purchase_order_id": purchase_order["id"],
                    "supplier": purchase_order["supplier_name"],
                    "total_cost": purchase_order["total_cost"]
                }
            }
        )

# Usage example
async def main():
    manager = AdvancedInventoryManager(
        api_key="your_api_key",
        base_url="https://api.auraconnect.com"
    )
    
    result = await manager.analyze_and_reorder(
        restaurant_id=1,
        forecast_days=7
    )
    
    print(f"Analysis complete: {result}")
    print(f"Created {len(result['orders'])} purchase orders")
    print(f"Total cost: ${result['total_cost']:,.2f}")

# Run the async function
asyncio.run(main())
```

## Staff Scheduling with Compliance

### Automated Schedule Generation with Labor Law Compliance
This example demonstrates creating staff schedules while ensuring compliance with labor laws and optimizing costs.

```javascript
class ComplianceAwareScheduler {
  constructor(apiKey, baseUrl) {
    this.apiKey = apiKey;
    this.baseUrl = baseUrl;
    this.headers = {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json'
    };
  }

  async generateWeeklySchedule(restaurantId, weekStartDate) {
    try {
      // Step 1: Get staffing requirements
      const requirements = await this.getStaffingRequirements(restaurantId, weekStartDate);
      
      // Step 2: Get available staff with constraints
      const staff = await this.getAvailableStaff(restaurantId);
      
      // Step 3: Get labor law constraints
      const constraints = await this.getLaborConstraints(restaurantId);
      
      // Step 4: Generate optimized schedule
      const schedule = await this.optimizeSchedule(
        requirements, 
        staff, 
        constraints, 
        weekStartDate
      );
      
      // Step 5: Validate compliance
      const validation = await this.validateCompliance(schedule, constraints);
      
      if (!validation.compliant) {
        throw new Error(`Schedule not compliant: ${validation.violations.join(', ')}`);
      }
      
      // Step 6: Submit schedule
      const result = await this.submitSchedule(restaurantId, schedule);
      
      return result;
      
    } catch (error) {
      console.error('Schedule generation failed:', error);
      throw error;
    }
  }

  async getStaffingRequirements(restaurantId, weekStartDate) {
    // Get forecasted needs based on historical data
    const response = await fetch(
      `${this.baseUrl}/api/v1/restaurants/${restaurantId}/staffing-requirements`,
      {
        headers: this.headers,
        method: 'POST',
        body: JSON.stringify({
          week_start: weekStartDate,
          use_ai_forecast: true,
          include_events: true
        })
      }
    );
    
    return response.json();
  }

  async getAvailableStaff(restaurantId) {
    const response = await fetch(
      `${this.baseUrl}/api/v1/restaurants/${restaurantId}/staff?active=true&include_availability=true`,
      { headers: this.headers }
    );
    
    const staff = await response.json();
    
    // Enhance with additional constraints
    return Promise.all(staff.map(async (employee) => {
      const constraints = await this.getEmployeeConstraints(employee.id);
      return { ...employee, constraints };
    }));
  }

  async getEmployeeConstraints(employeeId) {
    const response = await fetch(
      `${this.baseUrl}/api/v1/staff/${employeeId}/constraints`,
      { headers: this.headers }
    );
    
    return response.json();
  }

  async getLaborConstraints(restaurantId) {
    const response = await fetch(
      `${this.baseUrl}/api/v1/restaurants/${restaurantId}/labor-laws`,
      { headers: this.headers }
    );
    
    return response.json();
  }

  async optimizeSchedule(requirements, staff, constraints, weekStartDate) {
    const schedule = {
      week_start: weekStartDate,
      shifts: []
    };

    // For each day and shift requirement
    for (const dayReq of requirements.daily_requirements) {
      for (const shiftReq of dayReq.shifts) {
        const shift = await this.fillShift(
          shiftReq, 
          staff, 
          constraints, 
          schedule.shifts,
          dayReq.date
        );
        
        if (shift.assigned_staff.length < shift.required_staff) {
          console.warn(`Understaffed shift on ${dayReq.date} ${shiftReq.name}`);
        }
        
        schedule.shifts.push(shift);
      }
    }

    // Optimize for cost and fairness
    return this.balanceSchedule(schedule, staff, constraints);
  }

  async fillShift(shiftReq, staff, constraints, existingShifts, date) {
    const shift = {
      date: date,
      start_time: shiftReq.start_time,
      end_time: shiftReq.end_time,
      required_staff: shiftReq.required_staff,
      required_roles: shiftReq.required_roles,
      assigned_staff: []
    };

    // Sort staff by suitability
    const suitableStaff = this.rankStaffForShift(
      staff, 
      shift, 
      constraints, 
      existingShifts
    );

    // Assign staff while respecting constraints
    for (const employee of suitableStaff) {
      if (shift.assigned_staff.length >= shift.required_staff) break;
      
      if (this.canAssignToShift(employee, shift, constraints, existingShifts)) {
        shift.assigned_staff.push({
          employee_id: employee.id,
          employee_name: employee.name,
          role: employee.primary_role,
          hourly_rate: employee.hourly_rate
        });
      }
    }

    return shift;
  }

  rankStaffForShift(staff, shift, constraints, existingShifts) {
    return staff
      .map(employee => ({
        ...employee,
        score: this.calculateSuitabilityScore(employee, shift, existingShifts)
      }))
      .filter(emp => emp.score > 0)
      .sort((a, b) => b.score - a.score);
  }

  calculateSuitabilityScore(employee, shift, existingShifts) {
    let score = 100;

    // Check role match
    if (!shift.required_roles.includes(employee.primary_role)) {
      score -= 50;
    }

    // Check availability
    if (!this.isAvailable(employee, shift)) {
      return 0;
    }

    // Prefer employees with fewer hours (fairness)
    const currentHours = this.getEmployeeHours(employee.id, existingShifts);
    score -= currentHours * 2;

    // Consider employee preferences
    if (employee.preferred_shifts && !employee.preferred_shifts.includes(shift.start_time)) {
      score -= 20;
    }

    // Cost optimization (slightly prefer lower cost)
    score -= employee.hourly_rate * 0.5;

    return Math.max(0, score);
  }

  canAssignToShift(employee, shift, constraints, existingShifts) {
    // Check availability
    if (!this.isAvailable(employee, shift)) return false;

    // Check maximum hours per week
    const currentHours = this.getEmployeeHours(employee.id, existingShifts);
    const shiftHours = this.calculateShiftHours(shift);
    
    if (currentHours + shiftHours > constraints.max_hours_per_week) return false;

    // Check minimum rest between shifts
    const lastShift = this.getLastShift(employee.id, existingShifts);
    if (lastShift) {
      const restHours = this.calculateRestHours(lastShift, shift);
      if (restHours < constraints.min_rest_hours) return false;
    }

    // Check consecutive days limit
    const consecutiveDays = this.getConsecutiveDays(employee.id, existingShifts, shift.date);
    if (consecutiveDays >= constraints.max_consecutive_days) return false;

    // Minor-specific constraints
    if (employee.is_minor) {
      if (!this.checkMinorConstraints(employee, shift, constraints)) return false;
    }

    return true;
  }

  async validateCompliance(schedule, constraints) {
    const violations = [];

    for (const shift of schedule.shifts) {
      for (const assignment of shift.assigned_staff) {
        // Validate individual compliance
        const employeeShifts = schedule.shifts.filter(s => 
          s.assigned_staff.some(a => a.employee_id === assignment.employee_id)
        );

        // Check weekly hours
        const weeklyHours = employeeShifts.reduce((sum, s) => 
          sum + this.calculateShiftHours(s), 0
        );
        
        if (weeklyHours > constraints.max_hours_per_week) {
          violations.push(`Employee ${assignment.employee_name} exceeds weekly hours limit`);
        }

        // Check overtime rules
        if (weeklyHours > constraints.overtime_threshold) {
          const overtimeHours = weeklyHours - constraints.overtime_threshold;
          // Log for payroll calculation
          console.log(`Employee ${assignment.employee_name} has ${overtimeHours} overtime hours`);
        }
      }
    }

    return {
      compliant: violations.length === 0,
      violations: violations
    };
  }

  async submitSchedule(restaurantId, schedule) {
    const response = await fetch(
      `${this.baseUrl}/api/v1/restaurants/${restaurantId}/schedules`,
      {
        method: 'POST',
        headers: this.headers,
        body: JSON.stringify({
          ...schedule,
          auto_notify_staff: true,
          require_confirmation: true
        })
      }
    );

    const result = await response.json();

    // Send notifications to staff
    await this.notifyStaff(result.id);

    return result;
  }

  // Helper methods
  isAvailable(employee, shift) {
    // Check employee availability
    return employee.availability.some(avail => 
      avail.day === shift.date && 
      avail.start_time <= shift.start_time && 
      avail.end_time >= shift.end_time
    );
  }

  getEmployeeHours(employeeId, shifts) {
    return shifts
      .filter(shift => shift.assigned_staff.some(a => a.employee_id === employeeId))
      .reduce((sum, shift) => sum + this.calculateShiftHours(shift), 0);
  }

  calculateShiftHours(shift) {
    const start = new Date(`2000-01-01 ${shift.start_time}`);
    const end = new Date(`2000-01-01 ${shift.end_time}`);
    return (end - start) / (1000 * 60 * 60);
  }

  balanceSchedule(schedule, staff, constraints) {
    // Additional optimization for fairness and cost
    // This is a simplified version - real implementation would use more sophisticated algorithms
    
    const staffHours = {};
    
    // Calculate total hours per staff
    schedule.shifts.forEach(shift => {
      shift.assigned_staff.forEach(assignment => {
        staffHours[assignment.employee_id] = 
          (staffHours[assignment.employee_id] || 0) + this.calculateShiftHours(shift);
      });
    });

    // Log statistics
    console.log('Schedule Statistics:', {
      total_shifts: schedule.shifts.length,
      total_hours: Object.values(staffHours).reduce((a, b) => a + b, 0),
      average_hours_per_employee: 
        Object.values(staffHours).reduce((a, b) => a + b, 0) / Object.keys(staffHours).length,
      coverage_rate: this.calculateCoverageRate(schedule)
    });

    return schedule;
  }

  calculateCoverageRate(schedule) {
    const totalRequired = schedule.shifts.reduce((sum, s) => sum + s.required_staff, 0);
    const totalAssigned = schedule.shifts.reduce((sum, s) => sum + s.assigned_staff.length, 0);
    return (totalAssigned / totalRequired * 100).toFixed(2);
  }

  async notifyStaff(scheduleId) {
    await fetch(
      `${this.baseUrl}/api/v1/schedules/${scheduleId}/notify`,
      {
        method: 'POST',
        headers: this.headers,
        body: JSON.stringify({
          channels: ['email', 'sms', 'app'],
          require_confirmation: true,
          confirmation_deadline: '48h'
        })
      }
    );
  }
}

// Usage
const scheduler = new ComplianceAwareScheduler(
  'your_api_key',
  'https://api.auraconnect.com'
);

scheduler.generateWeeklySchedule(1, '2025-08-12')
  .then(schedule => {
    console.log('Schedule generated:', schedule);
    console.log(`Total shifts: ${schedule.shifts.length}`);
    console.log(`Coverage rate: ${schedule.coverage_rate}%`);
  })
  .catch(error => {
    console.error('Failed to generate schedule:', error);
  });
```

## Performance Optimization Tips

### Batch Operations
When dealing with multiple operations, use batch endpoints:

```python
# Instead of multiple individual requests
for item_id in item_ids:
    response = requests.get(f"/api/v1/items/{item_id}")
    # Process response

# Use batch endpoint
response = requests.post("/api/v1/items/batch", json={
    "ids": item_ids,
    "fields": ["id", "name", "price", "inventory"]
})
```

### Parallel Processing
Process independent operations concurrently:

```javascript
// Parallel processing with Promise.all
const [orders, inventory, staff] = await Promise.all([
  fetch('/api/v1/orders').then(r => r.json()),
  fetch('/api/v1/inventory').then(r => r.json()),
  fetch('/api/v1/staff').then(r => r.json())
]);

// Or with async/await
async function fetchDashboardData() {
  const promises = [
    fetchOrders(),
    fetchInventory(),
    fetchStaffStatus(),
    fetchAnalytics()
  ];
  
  const results = await Promise.allSettled(promises);
  
  return results.reduce((acc, result, index) => {
    if (result.status === 'fulfilled') {
      const keys = ['orders', 'inventory', 'staff', 'analytics'];
      acc[keys[index]] = result.value;
    }
    return acc;
  }, {});
}
```

### Pagination Best Practices
Always use pagination for large datasets:

```python
async def fetch_all_orders(start_date, end_date):
    all_orders = []
    page = 1
    per_page = 100
    
    while True:
        response = await fetch(
            f"/api/v1/orders",
            params={
                "start_date": start_date,
                "end_date": end_date,
                "page": page,
                "per_page": per_page
            }
        )
        
        data = response.json()
        all_orders.extend(data["items"])
        
        if page >= data["total_pages"]:
            break
            
        page += 1
    
    return all_orders
```