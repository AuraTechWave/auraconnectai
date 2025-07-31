import { field, children, writer, Q } from '@nozbe/watermelondb/decorators';
import BaseModel from './BaseModel';

export default class MenuCategory extends BaseModel {
  static table = 'menu_categories';
  static associations = {
    menu_items: { type: 'has_many', foreignKey: 'category_id' },
  } as const;

  @field('name') name!: string;
  @field('description') description?: string;
  @field('display_order') displayOrder!: number;
  @field('is_active') isActive!: boolean;

  @children('menu_items') items!: any;

  get itemCount() {
    return this.items.length;
  }

  @writer async reorder(newOrder: number) {
    await this.update(category => {
      category.displayOrder = newOrder;
      category.syncStatus = 'pending';
      category.lastModified = Date.now();
    });
  }

  @writer async toggleActive() {
    await this.update(category => {
      category.isActive = !category.isActive;
      category.syncStatus = 'pending';
      category.lastModified = Date.now();
    });
  }

  static active() {
    return this.query(
      Q.where('is_active', true),
      Q.where('is_deleted', false),
      Q.sortBy('display_order', Q.asc),
    );
  }
}