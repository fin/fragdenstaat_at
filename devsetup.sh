#!/bin/bash

if [ ! -d froide ]; then
  git clone --branch at-deploy --single-branch https://github.com/fin/froide.git
else
  pushd froide
  git pull
  popd
fi
