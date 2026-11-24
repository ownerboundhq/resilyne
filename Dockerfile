FROM node:22-bookworm-slim
WORKDIR /app
COPY package*.json ./
RUN npm install --omit=dev --ignore-scripts --no-audit --no-fund && npm cache clean --force
COPY --chown=node:node . .
USER node
ENV NODE_ENV=production
EXPOSE 3000
CMD ["npm","start"]
