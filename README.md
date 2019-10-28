Proper README still a work in progress...

**Usage**
1. Set up a Telegram account and get a bot API key.
* Set up a SQL database (see db_schema folder)
* Create in credentials.py (use credentials_empty.py as template)
* Run `start_bot.py`

Notes
* Databse is postgres

Setting up on Raspberry Pi

If using postgres, install libpq-dev

If using cloud_sql_proxy
Install go (should be 1.10+ if I'm not mistaken)

https://gist.github.com/pcgeek86/0206d688e6760fe4504ba405024e887c
just change version number, script should work

Build cloud_sql_proxy
https://github.com/GoogleCloudPlatform/cloudsql-proxy
go get github.com/GoogleCloudPlatform/cloudsql-proxy/cmd/cloud_sql_proxy
