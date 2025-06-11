# Payroll Module Architecture

## Overview
Automates salary calculation, shift tracking, bonuses, and payslip generation.

## System Flow
- Staff shifts logged (clock-in/out)
- Base hours and overtime calculated
- Bonuses/tips added
- AI Agent checks wage fairness/compliance
- Payslip generated and archived

## Key Components
- Payroll Engine
- Shift Logger
- Payslip Generator
- Compliance Agent

## Developer Notes
Each component should follow service-layer design with unit test coverage.
