#!/bin/bash

if [ ! -d froide ]; then
  git clone --branch fix-migrations-for-at --single-branch https://github.com/fin/froide.git
else
  pushd froide
  git pull
  popd
fi
