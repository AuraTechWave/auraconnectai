# backend/modules/menu/services/recipe_circular_validation.py

"""
Enhanced circular dependency validation for recipes.
Provides detailed detection and reporting of circular references in recipe hierarchies.
"""

from typing import Set, List, Dict, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
import json
import redis
from datetime import timedelta
from core.config import settings
from ..models.recipe_models import Recipe, RecipeSubRecipe


class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected in recipes"""

    def __init__(self, message: str, cycle_path: List[int] = None):
        super().__init__(message)
        self.cycle_path = cycle_path or []


class RecipeCircularValidator:
    """Validates and detects circular dependencies in recipe hierarchies"""

    def __init__(self, db: Session, redis_client: Optional[redis.Redis] = None):
        self.db = db
        self._dependency_cache = {}
        self._redis = redis_client
        self._cache_ttl = timedelta(minutes=15)  # 15 minute TTL for dependency trees
        self._cache_prefix = "recipe_deps:"

    def validate_no_circular_reference(
        self,
        parent_recipe_id: int,
        potential_sub_recipe_id: int,
        existing_sub_recipe_ids: List[int] = None,
    ) -> None:
        """
        Validate that adding a sub-recipe won't create a circular reference.

        Args:
            parent_recipe_id: The recipe that will contain the sub-recipe
            potential_sub_recipe_id: The recipe to be added as a sub-recipe
            existing_sub_recipe_ids: List of sub-recipe IDs already being added (for batch operations)

        Raises:
            CircularDependencyError: If adding the sub-recipe would create a cycle
        """
        # Check if they're the same (self-reference)
        if parent_recipe_id == potential_sub_recipe_id:
            raise CircularDependencyError(
                f"Recipe cannot reference itself as a sub-recipe",
                cycle_path=[parent_recipe_id],
            )

        # Build the dependency graph starting from the potential sub-recipe
        cycle_path = self._find_cycle_path(
            start_id=potential_sub_recipe_id,
            target_id=parent_recipe_id,
            existing_sub_recipe_ids=existing_sub_recipe_ids,
        )

        if cycle_path:
            # Create a readable error message
            recipe_names = self._get_recipe_names(cycle_path)
            path_str = " → ".join(recipe_names)

            raise CircularDependencyError(
                f"Adding this sub-recipe would create a circular dependency: {path_str}",
                cycle_path=cycle_path,
            )

    def validate_recipe_hierarchy(self, recipe_id: int) -> Dict[str, any]:
        """
        Validate the entire hierarchy of a recipe and return a report.

        Returns:
            Dict containing:
                - is_valid: bool
                - cycles: List of detected cycles
                - depth: Maximum depth of the recipe tree
                - total_sub_recipes: Total number of sub-recipes (including nested)
        """
        visited = set()
        cycles = []

        def dfs(current_id: int, path: List[int], depth: int) -> Tuple[int, int]:
            """Depth-first search to find cycles and calculate metrics"""
            if current_id in path:
                # Found a cycle
                cycle_start = path.index(current_id)
                cycle = path[cycle_start:] + [current_id]
                cycles.append(cycle)
                return depth, 0

            if current_id in visited:
                return depth, 0

            visited.add(current_id)
            path.append(current_id)

            # Get all sub-recipes
            sub_links = (
                self.db.query(RecipeSubRecipe)
                .filter(
                    RecipeSubRecipe.parent_recipe_id == current_id,
                    RecipeSubRecipe.is_active == True,
                )
                .all()
            )

            max_depth = depth
            total_count = len(sub_links)

            for link in sub_links:
                sub_depth, sub_count = dfs(link.sub_recipe_id, path.copy(), depth + 1)
                max_depth = max(max_depth, sub_depth)
                total_count += sub_count

            return max_depth, total_count

        max_depth, total_sub_recipes = dfs(recipe_id, [], 0)

        return {
            "is_valid": len(cycles) == 0,
            "cycles": cycles,
            "depth": max_depth,
            "total_sub_recipes": total_sub_recipes,
            "recipe_id": recipe_id,
        }

    def get_all_dependencies(self, recipe_id: int) -> Set[int]:
        """
        Get all recipe IDs that this recipe depends on (recursively).
        Uses Redis cache if available for performance.

        Returns:
            Set of recipe IDs that are dependencies
        """
        # Check Redis cache first
        if self._redis:
            cache_key = f"{self._cache_prefix}deps:{recipe_id}"
            cached = self._redis.get(cache_key)
            if cached:
                return set(json.loads(cached))

        # Check local cache
        if recipe_id in self._dependency_cache:
            return self._dependency_cache[recipe_id].copy()

        dependencies = set()
        to_process = [recipe_id]
        processed = set()

        while to_process:
            current_id = to_process.pop()
            if current_id in processed:
                continue

            processed.add(current_id)

            # Get direct sub-recipes
            sub_links = (
                self.db.query(RecipeSubRecipe)
                .filter(
                    RecipeSubRecipe.parent_recipe_id == current_id,
                    RecipeSubRecipe.is_active == True,
                )
                .all()
            )

            for link in sub_links:
                dependencies.add(link.sub_recipe_id)
                to_process.append(link.sub_recipe_id)

        # Cache the result
        self._dependency_cache[recipe_id] = dependencies.copy()

        # Store in Redis if available
        if self._redis:
            cache_key = f"{self._cache_prefix}deps:{recipe_id}"
            self._redis.setex(
                cache_key,
                self._cache_ttl.total_seconds(),
                json.dumps(list(dependencies)),
            )

        return dependencies

    def get_all_dependents(self, recipe_id: int) -> Set[int]:
        """
        Get all recipe IDs that depend on this recipe (recursively).

        Returns:
            Set of recipe IDs that are dependents
        """
        dependents = set()
        to_process = [recipe_id]
        processed = set()

        while to_process:
            current_id = to_process.pop()
            if current_id in processed:
                continue

            processed.add(current_id)

            # Get recipes that use this as a sub-recipe
            parent_links = (
                self.db.query(RecipeSubRecipe)
                .filter(
                    RecipeSubRecipe.sub_recipe_id == current_id,
                    RecipeSubRecipe.is_active == True,
                )
                .all()
            )

            for link in parent_links:
                dependents.add(link.parent_recipe_id)
                to_process.append(link.parent_recipe_id)

        return dependents

    def _find_cycle_path(
        self, start_id: int, target_id: int, existing_sub_recipe_ids: List[int] = None
    ) -> Optional[List[int]]:
        """
        Find if there's a path from start_id to target_id in the dependency graph.

        Returns:
            List representing the cycle path if found, None otherwise
        """
        visited = set()
        path = []

        def dfs(current_id: int) -> bool:
            if current_id == target_id:
                path.append(current_id)
                return True

            if current_id in visited:
                return False

            visited.add(current_id)
            path.append(current_id)

            # Get sub-recipes from database
            sub_links = (
                self.db.query(RecipeSubRecipe)
                .filter(
                    RecipeSubRecipe.parent_recipe_id == current_id,
                    RecipeSubRecipe.is_active == True,
                )
                .all()
            )

            # Check existing sub-recipes
            for link in sub_links:
                if dfs(link.sub_recipe_id):
                    return True

            # Also check sub-recipes being added in this transaction
            if existing_sub_recipe_ids and current_id == start_id:
                for sub_id in existing_sub_recipe_ids:
                    if sub_id != potential_sub_recipe_id and dfs(sub_id):
                        return True

            path.pop()
            return False

        if dfs(start_id):
            return path

        return None

    def _get_recipe_names(self, recipe_ids: List[int]) -> List[str]:
        """Get recipe names with menu item names for a list of IDs"""
        from core.menu_models import MenuItem

        # Query recipes with their menu items
        recipes = (
            self.db.query(Recipe)
            .options(self.db.query(Recipe).joinedload(Recipe.menu_item))
            .filter(Recipe.id.in_(recipe_ids))
            .all()
        )

        recipe_map = {}
        for r in recipes:
            if r.menu_item:
                # Include both recipe name and menu item name for clarity
                recipe_map[r.id] = f"{r.menu_item.name} ({r.name})"
            else:
                recipe_map[r.id] = r.name

        return [recipe_map.get(rid, f"Recipe#{rid}") for rid in recipe_ids]

    def clear_cache(self, recipe_id: Optional[int] = None):
        """Clear the dependency cache for a specific recipe or all recipes"""
        if recipe_id:
            # Clear specific recipe from local cache
            self._dependency_cache.pop(recipe_id, None)

            # Clear from Redis if available
            if self._redis:
                self._redis.delete(f"{self._cache_prefix}deps:{recipe_id}")
                # Also clear dependent recipes cache
                for dep_id in self.get_all_dependents(recipe_id):
                    self._redis.delete(f"{self._cache_prefix}deps:{dep_id}")
        else:
            # Clear all caches
            self._dependency_cache.clear()

            # Clear all recipe dependency keys from Redis
            if self._redis:
                pattern = f"{self._cache_prefix}*"
                for key in self._redis.scan_iter(match=pattern):
                    self._redis.delete(key)

    def validate_batch_sub_recipes(
        self, parent_recipe_id: int, sub_recipe_data: List[Dict[str, any]]
    ) -> None:
        """
        Validate a batch of sub-recipes before adding them.

        Args:
            parent_recipe_id: The parent recipe ID
            sub_recipe_data: List of dicts with 'sub_recipe_id' key

        Raises:
            CircularDependencyError: If any sub-recipe would create a cycle
            ValueError: For other validation errors
        """
        sub_recipe_ids = [data["sub_recipe_id"] for data in sub_recipe_data]

        # Check for duplicates
        if len(sub_recipe_ids) != len(set(sub_recipe_ids)):
            duplicates = [id for id in sub_recipe_ids if sub_recipe_ids.count(id) > 1]
            raise ValueError(f"Duplicate sub-recipes found: {duplicates}")

        # Check each sub-recipe
        for data in sub_recipe_data:
            sub_recipe_id = data["sub_recipe_id"]

            # Validate the sub-recipe exists
            sub_recipe = (
                self.db.query(Recipe)
                .filter(Recipe.id == sub_recipe_id, Recipe.deleted_at.is_(None))
                .first()
            )

            if not sub_recipe:
                raise ValueError(f"Sub-recipe {sub_recipe_id} not found")

            # Check for circular reference
            self.validate_no_circular_reference(
                parent_recipe_id, sub_recipe_id, sub_recipe_ids
            )
