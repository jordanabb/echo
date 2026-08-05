"""Helpers behind scripts/echo.py.

Split by concern so no single file becomes unreadable:

  console.py     terminal output and prompting
  config.py      paths, .env.deploy, database target resolution
  aws.py         AWS CLI wrapper and the MFA session
  preflight.py   environment check
  data.py        S3 sync of ETL inputs and dumps
  database.py    dump, restore, verify, snapshot
  indicators.py  keeping indicator_config.py in step with the database
  deploy.py      backend and frontend deploys
"""
