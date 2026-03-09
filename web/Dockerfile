FROM golang:1.23-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
# If go.sum doesn't exist yet, download will still work
RUN go mod download || true

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o main .

FROM alpine:latest
WORKDIR /app

# Copy the built executable
COPY --from=builder /app/main .
# Copy the templates
COPY --from=builder /app/templates ./templates

# Expose port
EXPOSE 8083

CMD ["./main"]
