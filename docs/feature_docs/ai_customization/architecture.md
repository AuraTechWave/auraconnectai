# Ai Customization Module Architecture

## Overview
Trains agents on restaurant-specific data (menus, reviews, behavior).

## System Flow
- Restaurant uploads datasets
- Data preprocessed into embeddings/prompts
- Fine-tuned agents generated
- Stored and assigned to tenant
- Used in live chat/menu interactions

## Key Components
- Dataset Importer
- Prompt Trainer
- Agent Registry
- Embed Store

## Developer Notes
Each component should follow service-layer design with unit test coverage.
