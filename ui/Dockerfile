FROM node:20-slim
WORKDIR /app
COPY ui/package.json /app/package.json
RUN npm install || true
COPY ui/ /app/
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
