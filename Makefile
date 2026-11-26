export DJANGO_SETTINGS_MODULE=fragdenstaat_at.settings.test
export DJANGO_CONFIGURATION=Test
export PYTHONWARNINGS=ignore,default:::fragdenstaat_at

RUN = uv run --no-sync

test:
	$(RUN) ruff check
	$(RUN) pytest --reuse-db

testci:
	coverage run --branch -m pytest --reuse-db
	coverage report

backend_dependencies:
	./devsetup.sh upgrade_backend_repos

frontend_dependencies:
	./devsetup.sh upgrade_frontend_repos

dependencies: backend_dependencies frontend_dependencies

commitdependencies: dependencies
	git add uv.lock pnpm-lock.yaml
	git commit -m "Update dependencies"

MAKEMESSAGES_OPTS = --ignore public --ignore froide-env --ignore node_modules --ignore htmlcov --ignore src --add-location file --no-wrap --sort-output --keep-header
MAKEMESSAGES_EXTRA_OPTS =

messagesde:
	$(RUN) python manage.py extendedmakemessages -l de $(MAKEMESSAGES_OPTS) $(MAKEMESSAGES_EXTRA_OPTS)

messagesls:
	$(RUN) python manage.py extendedmakemessages -l de_LS $(MAKEMESSAGES_OPTS)

checkmessagesde:
	$(MAKE) messagesde MAKEMESSAGES_EXTRA_OPTS="--no-untranslated --no-fuzzy"

run_frontend_server:
	pnpm run dev --host=0.0.0.0
