<p align="center">
  <br/>
  <a href="https://www.python.org">
    <img src="https://img.shields.io/badge/Python-FFD43B?style=for-the-badge&logo=python&logoColor=blue"
    alt="Python"/>
  </a>
  <a href="https://docs.celeryq.dev/en/stable/getting-started/introduction.html">
    <img src="https://img.shields.io/badge/celery-%23a9cc54.svg?style=for-the-badge&logo=celery&logoColor=ddf4a4"
    alt="Celery"/>
  </a>
  <a href="https://docs.pydantic.dev/latest/">
    <img src="https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=Pydantic&logoColor=white"
    alt="Pydantic"/>
  </a>
  <a href="https://sqlite.org">
    <img src="https://img.shields.io/badge/Sqlite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite">
  </a>
  <a href="https://playwright.dev/python/">
    <img src="https://img.shields.io/badge/Playwright-45ba4b?style=for-the-badge&logo=Playwright&logoColor=white"
    alt="Playwright"/>
  </a>
  <a href="https://docs.docker.com/compose/">
    <img src="https://img.shields.io/badge/Docker%20Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker Compose"/>
  </a>
  <br/>
  <br/>
</p>

# Realty Alerts

Realty Alerts is a simple alerting tool for notifying when new homes become available for purchase on Dutch real estate websites, such as Funda.nl.

<div align="center">
    <img src="./assets/images/app-example.jpg" >
</div>

## Key Features

- Queries for each website can be added through an intuitive UI
- Notifications can be received through NTFY (app available on Android/iOS)
- Only new house offers will be notified. The ones that already have been notified won't repeat again.
- Deployment of the whole tool can be easily done with a docker compose file.

## Supported Websites

- Funda: https://www.funda.nl
- Pararius: https://www.pararius.nl
- Vastgoed Nederland: https://aanbod.vastgoednederland.nl

> [!NOTE]
> Only the list of websites above is currently available for scraping. Other websites (e.g. real estate brokers) will be supported on request (Github issue).


## App setup

1. Download the NTFY app from the [Play Store](https://play.google.com/store/apps/details?id=io.heckel.ntfy) (Android) or from the [App Store](https://apps.apple.com/us/app/ntfy/id1625396347) (iOS)
2. Click on the plus icon to add a new topic. Write a creative one, to avoid other people pushing to your topic. All topics on the `https://ntfy.sh` server are public, so if you wish, you can also use your own NTFY server for more privacy. If doing so, please check the following [link](https://docs.ntfy.sh/install/), and don't forget to add the [environment variable](#additional-configuration) `NTFY_URL` in the docker compose file.


## How to use

1. Check if docker is installed. If not, follow the guidelines in the [official website](https://docs.docker.com/engine/install/).
2. Copy the `docker-compose.yml` file from this repo.
3. Create a `data` folder in the same directory where the `docker-compose.yml` file is.
4. If needed, configure any environment variables in the docker compose file. Please check [below](#additional-configuration)
5. Run the command:

```bash
docker compose up -d
```

6. Access the UI through the URL: http://localhost:9000
7. Add new queries. Each query requires a listing url with active filters of one of the [suported websites](#supported-websites). Also, don't forget to include your NTFY topic (see [app setup](#app-setup)).
8. Before saving a new query, run the test command, to see if everything is working as expected. If not, please check the docker compose logs.
8. Everything is set! You will receive a notifications of new houses per defined query, on the desired time schedule.


## Additional configuration

Realty Alerts can be run as is, without any additional configuration. But in case needed, environment variables can be set. Here is a list of them and their default values:

| Env variable | Default value                 |
| ------------ | ----------------------------- |
| NTFY_URL     | https://ntfy.sh               |
| REDIS_URL    | redis://localhost:6379/0      |
| BROWSER_URL  | ws://localhost:3000           |
| TIMEZONE     | Europe/Amsterdam              |
