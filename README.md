# Nexus_Domain_Organization
Organized domains, subdomains, indicators and data from the related papers

# Literature Catalog

This repository stores structured metadata of research papers in YAML format.  
Each paper file contains fields such as `domain`, `subdomain`, `indicators`, and `data`.

## Structure
- `papers/` : one YAML file per paper
- `schema/` : JSON schema definitions for validation
- `taxonomy/` : domain and subdomain definitions
- `scripts/` : Python scripts to validate/query data
- `build/` : generated CSV/JSON outputs

## Usage
Run validation:ß
```bash
python scripts/validate.py
