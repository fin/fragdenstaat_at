FROM fragdenstaat_at-baseimage

COPY froide /code/code/froide
RUN pip uninstall -y froide && pip install -e /code/code/froide/

COPY yarn.lock /code/code/
COPY package.json /code/code/
COPY tsconfig.json /code/code/


RUN cd /code/code/froide && npm install -g yarn && yarn install && yarn link
RUN cd /code/code/ && yarn install
RUN cd /code/code/ && yarn link froide


COPY .babelrc /code/code/
COPY manage.py /code/code/
COPY webpack.config.js /code/code/
COPY Procfile.dev /code/code/

WORKDIR /code/code
