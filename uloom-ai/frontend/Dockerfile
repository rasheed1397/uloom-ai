# Multi-stage: build the static bundle with Node, serve it with nginx - the
# built output has no runtime Node dependency at all.
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# VITE_API_BASE_URL isn't set here on purpose: the built bundle runs in the
# *browser*, not inside this container's network, so it must point at
# wherever the api service is reachable from the host (defaults to
# http://localhost:8000 in src/api/client.ts, which matches api's published
# port in docker-compose.yml) - not an internal Docker DNS name like
# "http://api:8000", which the browser could never resolve.
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
