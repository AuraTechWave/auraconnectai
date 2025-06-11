# POS Integration Module

## Summary
Connects external POS systems like Toast and Square with AuraConnect’s backend.

## Key Features
- Webhooks for order/payment sync
- POS adapter abstraction layer
- Order reconciliation dashboard

## Developer Notes
- Adapter logic: `modules/pos_integration/adapters/`
- Sync service: `pos_sync_service.py`
