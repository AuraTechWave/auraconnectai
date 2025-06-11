# Tax Module

## Summary
Manages GST/VAT tax rules per region, calculates item-level tax, and generates audit reports.

## Key Features
- Dynamic tax rules per location/item
- AI optimization for billing structures
- Downloadable monthly tax reports

## Developer Notes
- Logic: `backend/services/tax_service.py`
- Agent: `ai_agents/tax_agent.py`
- Models: `TaxRule`, `Invoice`, `TaxRecord`
