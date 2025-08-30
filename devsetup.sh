#!/bin/bash
set -ex

MAIN=fragdenstaat_at
# REPOS=("froide" "froide-campaign" "froide-legalaction" "froide-food" "froide-payment" "froide-crowdfunding" "froide-govplan" "froide-fax" "froide-exam" "django-filingcabinet")
REPOS=("froide" "froide-payment" "django-filingcabinet" )
# FRONTEND_DIR=("froide" "froide_food" "froide_exam" "froide_campaign" "froide_payment" "froide_legalaction" "filingcabinet")
FRONTEND_DIR=("froide" "froide-payment" "django-filingcabinet")
# FRONTEND=("froide" "froide_food" "froide_exam" "froide_campaign" "froide_payment" "froide_legalaction" "@okfde/filingcabinet")
FRONTEND=("froide" "froide_payment" "@okfde/filingcabinet")
FRONTEND_DEPS=("froide" "@okfde/filingcabinet")
FROIDE_PEERS=("froide-campaign" "froide-food")


ask() {
    # https://djm.me/ask
    local prompt default reply

    if [ "${2:-}" = "Y" ]; then
        prompt="Y/n"
        default=Y
    elif [ "${2:-}" = "N" ]; then
        prompt="y/N"
        default=N
    else
        prompt="y/n"
        default=
    fi

    while true; do

        # Ask the question (not using "read -p" as it uses stderr not stdout)
        echo -n "$1 [$prompt] "

        # Read the answer (use /dev/tty in case stdin is redirected from somewhere else)
        read reply </dev/tty

        # Default?
        if [ -z "$reply" ]; then
            reply=$default
        fi

        # Check if the reply is valid
        case "$reply" in
            Y*|y*) return 0 ;;
            N*|n*) return 1 ;;
        esac

    done
}

install_precommit() {
  local repo_dir="$1"
  if [ -e "$repo_dir/.pre-commit-config.yaml" ]; then
    pushd "$repo_dir"
    pre-commit install
    popd
  fi
}

setup() {

  echo "You need python3 >= 3.8 and yarn installed."

  python3 --version
  yarn --version
  uv --version

  if [ ! -d fds-env ]; then
    if ask "Do you want to create a virtual environment using $(python3 --version)?" Y; then
      echo "Creating virtual environment with Python: $(python3 --version)"
      uv venv fds-env
    fi
  fi

  if [ ! -d fds-env ]; then
    echo "Could not find virtual environment fds-env"
  fi

  echo "Activating virtual environment..."
  source fds-env/bin/activate

  echo "Cloning / installing $MAIN"

  if [ ! -d $MAIN ]; then
    git clone git@github.com:fin/$MAIN.git
  else
    pushd $MAIN
      git pull origin "$(git branch --show-current)"
    popd
  fi


  for name in "${REPOS[@]}"; do
    if [ ! -d $name ]; then
      git clone git@github.com:okfde/$name.git
    else
      pushd $name
        git pull origin "$(git branch --show-current)"
      popd
    fi
  done

  #pip install -U pip-tools
  #pip-sync $MAIN/requirements-dev.txt
  uv pip install -r $MAIN/requirements-dev.txt
  #pip install -e $MAIN
  install_precommit "$MAIN"

  echo "Cloning / installing all editable dependencies..."

  for name in "${REPOS[@]}"; do
    uv pip install -e "./$name" --config-setting editable_mode=compat
    install_precommit "$name"
  done

  echo "Installing all frontend dependencies..."

  frontend

  fds-env/bin/python fragdenstaat_at/manage.py compilemessages -l de

  echo "Done."
}


messages() {
  fds-env/bin/python fragdenstaat_de/manage.py compilemessages -l de -i node_modules
}

frontend() {
  echo "Linking frontend dependencies..."

  echo "Installing frontend dependencies..."
  for name in "${FRONTEND_DIR[@]}"; do
    pushd "$name"
    if ! pnpm list -g --depth=0 | grep -q "$name"; then
        pnpm link --global
    fi
    pnpm install
    popd
  done

  pushd "$MAIN"
  pnpm install
  for name in "${FRONTEND[@]}"; do
    if ! pnpm list -g --depth=0 | grep -q "$name"; then
        pnpm link --global "$name"
    fi
  done
  popd
}

forall() {
  echo "Executing '$@' in all repos"
  pushd $MAIN
    "$@"
  popd

  for name in "${REPOS[@]}"; do
    pushd $name
      "$@"
    popd
  done
}

help() {
  echo "Available commands:"
  echo "setup: setup / update all repos"
  echo "forall: run command in all repos"
}


if [[ $1 =~ ^(forall)$ ]]; then
  "$@"
elif [[ $1 =~ ^(frontend)$ ]]; then
  frontend
else
  setup
fi
