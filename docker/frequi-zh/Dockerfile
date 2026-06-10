# syntax=docker/dockerfile:1

ARG FREQUI_REPO=https://github.com/freqtrade/frequi.git
ARG FREQUI_REF=3.0.2

FROM node:22-alpine AS build

ARG FREQUI_REPO
ARG FREQUI_REF

WORKDIR /src

RUN apk add --no-cache git \
  && git clone --depth 1 --branch "${FREQUI_REF}" "${FREQUI_REPO}" . \
  && corepack enable

COPY docker/frequi-zh/zh-cn-overlay.js /tmp/zh-cn-overlay.js

RUN pnpm install --frozen-lockfile \
  && pnpm build \
  && cp /tmp/zh-cn-overlay.js dist/zh-cn-overlay.js \
  && grep -q "</body>" dist/index.html \
  && sed -i 's#</body>#<script src="/zh-cn-overlay.js"></script></body>#' dist/index.html \
  && printf "frequi-%s-zh-cn\n" "${FREQUI_REF}" > dist/ui_version

FROM nginx:1.27-alpine

COPY docker/nginx/frequi.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist/ /usr/share/nginx/html/
