# Realty Alerts

Realty Alerts is a simple alerting tool for notifying when new homes become available for purchase on Dutch real estate websites, such as Funda.nl.

## Key Features
- Filters for each type of house queries can be added with simple YAML files, including scheduling of queries.
- Notifications can be received through NTFY (app a.vailable on Android)
- Only new house offers will be notified. The ones that already have been notified won't repeat again.
- Deployment of the whole tool can be easily done with a docker compose file.


## How to Install

1. Check if docker is installed. If not, follow the guidelines in the [official website](https://docs.docker.com/engine/install/)
2. Copy the `docker-compose.yml` file from this repo
3. Run the command:

```bash
docker compose up -d
```

## Additional configuration

Realty Alerts can be run as is, without any additional configuration. But in case needed, environment variables can be set. Here is a list of them and their default values:

| Env variable | Default value            |
| ------------ | ------------------------ |
| REDIS_URL    | redis://localhost:6379/0 |
| TIMEZONE     | Europe/Amsterdam         |
