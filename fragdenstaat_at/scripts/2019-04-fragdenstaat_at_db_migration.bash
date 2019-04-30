#echo "DROP DATABASE fragdenstaat;" | psql -U postgres -h localhost -p 5432 postgres

#psql -U postgres -h localhost -p 5432 postgres < pg_backup.sql

echo "ALTER TABLE auth_user RENAME TO account_user" | python manage.py dbshell

python manage.py migrate --fake-initial publicbody 0009
python manage.py migrate --fake publicbody 0010


python manage.py migrate --fake-initial foirequest 0001
python manage.py migrate --fake foirequest 0002
python manage.py migrate foirequest 0030

python manage.py migrate --fake-initial


# sqldiff
# - account: account_user_groups, account_user_user_permissions
# - publicbody: classifications
# - foirequestfollower: Index

python manage.py sqldiff -a | python manage.py dbshell

# python manage.py loaddata fragdenstaat_at/test.json
