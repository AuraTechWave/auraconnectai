# Tax Module Architecture

## Overview
Calculates and applies GST/VAT based on region, item, and service type.

## System Flow
- Order placed with taxable items
- Tax rules applied from config
- AI Agent optimizes tax efficiency
- Tax breakdown shown in invoice
- Monthly reports generated

## Key Components
- Tax Rule Engine
- Invoice Builder
- AI Tax Optimizer
- Report Generator

## Developer Notes
Each component should follow service-layer design with unit test coverage.
