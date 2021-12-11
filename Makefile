export DJANGO_SETTINGS_MODULE=fragdenstaat_at.settings.test
export DJANGO_CONFIGURATION=Test
export PYTHONWARNINGS=ignore,default:::fragdenstaat_at

test:
	flake8 fragdenstaat_at
	python manage.py test tests --keepdb

testci:
	python manage.py test tests --keepdb
