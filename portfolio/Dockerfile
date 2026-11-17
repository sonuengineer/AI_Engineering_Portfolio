# Build context must be the WORKSPACE ROOT so the sync step can read the three projects' artifacts:
#   docker build -f portfolio/Dockerfile -t portfolio .
FROM node:24-alpine AS build
WORKDIR /ws
COPY nexus-ai/docs nexus-ai/docs
COPY nexus-ai/interview-preparation nexus-ai/interview-preparation
COPY datawise-ai/docs datawise-ai/docs
COPY datawise-ai/interview-preparation datawise-ai/interview-preparation
COPY evalops-ai/docs evalops-ai/docs
COPY evalops-ai/interview-preparation evalops-ai/interview-preparation
COPY interview-preparation interview-preparation
COPY portfolio/package.json portfolio/package-lock.json portfolio/
RUN cd portfolio && npm ci --ignore-scripts
COPY portfolio portfolio
RUN cd portfolio && npm run build

FROM nginx:1.29-alpine
COPY portfolio/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /ws/portfolio/dist /usr/share/nginx/html
EXPOSE 80
