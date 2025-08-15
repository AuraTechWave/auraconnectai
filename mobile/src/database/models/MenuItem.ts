import {
  field,
  relation,
  json,
  writer,
  Q,
} from '@nozbe/watermelondb/decorators';
import BaseModel from './BaseModel';

interface MenuModifier {
  id: string;
  name: string;
  options: Array<{
    id: string;
    name: string;
    price: number;
  }>;
  required: boolean;
  maxSelections: number;
}

export default class MenuItem extends BaseModel {
  static table = 'menu_items';
  static associations = {
    menu_categories: { type: 'belongs_to', key: 'category_id' },
    order_items: { type: 'has_many', foreignKey: 'menu_item_id' },
  } as const;

  @field('category_id') categoryId!: string;
  @field('name') name!: string;
  @field('description') description?: string;
  @field('price') price!: number;
  @field('cost') cost?: number;
  @field('image_url') imageUrl?: string;
  @field('is_available') isAvailable!: boolean;
  @field('preparation_time') preparationTime?: number;
  @json('tags', json => json || []) tags!: string[];
  @json('modifiers', json => json || []) modifiers!: MenuModifier[];

  @relation('menu_categories', 'category_id') category!: any;

  get margin(): number {
    if (!this.cost) return 0;
    return ((this.price - this.cost) / this.price) * 100;
  }

  get hasModifiers(): boolean {
    return this.modifiers.length > 0;
  }

  get requiredModifiers(): MenuModifier[] {
    return this.modifiers.filter(mod => mod.required);
  }

  @writer async toggleAvailability() {
    await this.update(item => {
      item.isAvailable = !item.isAvailable;
      item.syncStatus = 'pending';
      item.lastModified = Date.now();
    });
  }

  @writer async updatePrice(newPrice: number) {
    await this.update(item => {
      item.price = newPrice;
      item.syncStatus = 'pending';
      item.lastModified = Date.now();
    });
  }

  static available() {
    return this.query(
      Q.where('is_available', true),
      Q.where('is_deleted', false),
    );
  }

  static byCategory(categoryId: string) {
    return this.query(
      Q.where('category_id', categoryId),
      Q.where('is_deleted', false),
      Q.sortBy('name', Q.asc),
    );
  }

  static search(term: string) {
    return this.query(
      Q.where('name', Q.like(`%${Q.sanitizeLikeString(term)}%`)),
      Q.where('is_deleted', false),
    );
  }
}
