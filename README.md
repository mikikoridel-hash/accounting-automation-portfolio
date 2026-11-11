# Invoice Automation Demo

## Overview
A portfolio project demonstrating how manual invoice preparation can be streamlined through data consolidation, transformation, and automated generation of NetSuite-ready CSV import files.

Inspired by real-world accounting workflow improvement experience, this project uses entirely synthetic data and independently developed examples.

## The Problem
Invoice preparation often involves multiple spreadsheets, inconsistent data structures, and manual entry of billing details such as regular hours, overtime, charge premiums, and internal IDs.

Preparing this data for ERP import can require additional mapping, formatting, and validation.

## Project Goals
- Consolidate weekly timesheet data into a clean dataset.
- Standardize agency, facility, and billing information.
- Apply billing rules for regular hours, overtime, double time, and charge premiums.
- Map billing details to sample internal IDs.
- Generate CSV files structured for a simulated NetSuite invoice import workflow.
- Validate required fields, data formats, and billing calculations before export.
- Support monthly billing analysis and reporting.

## Planned Workflow
1. Import sample weekly timesheets.
2. Clean and consolidate source data using Power Query.
3. Apply billing calculations and internal ID mapping.
4. Select an agency and billing date range.
5. Generate an invoice-ready CSV file.
6. Validate the output against a documented sample NetSuite import mapping.

## Tools
- Microsoft Excel
- Power Query / Power BI
- CSV
- NetSuite CSV Import Mapping (simulated)

## Status
In development. Sample datasets, transformation logic, CSV output, and validation documentation will be added progressively.

## Data Privacy
This repository uses fictional organizations, synthetic billing data, and independently developed examples. No employer-owned files, confidential information, production records, or actual NetSuite account information are included.

## Important Note
The exported CSV will demonstrate a NetSuite-oriented import structure. Actual compatibility depends on the target NetSuite account's configuration, required fields, custom forms, internal IDs, and import mappings. Live NetSuite import functionality is not claimed or tested in this demo.
