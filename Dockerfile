FROM node:22-alpine
ENV NODE_ENV=production HOST=0.0.0.0 PORT=4305
WORKDIR /app
COPY --chown=node:node package.json server.mjs ./
COPY --chown=node:node lib ./lib
COPY --chown=node:node bin ./bin
COPY --chown=node:node public ./public
USER node
EXPOSE 4305
CMD ["node", "server.mjs"]
