export DJANGO_SETTINGS_MODULE=fragdenstaat_at.settings.test
export DJANGO_CONFIGURATION=Test
export PYTHONWARNINGS=ignore,default:::fragdenstaat_at

test:
	flake8 fragdenstaat_at
	pytest --reuse-db

testci:
	coverage run --branch -m pytest --reuse-db
	coverage report

requirements: requirements.in requirements-dev.in requirements-production.in
	pip-compile requirements.in
	pip-compile requirements-dev.in
	pip-compile requirements-production.in

messagesde:
	django-admin makemessages -l de --ignore public --ignore froide-env --ignore node_modules --ignore htmlcov --add-location file
