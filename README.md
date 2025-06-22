# Realty Alerts

Realty Alerts is a simple alerting tool for notifying when new homes become available for purchase on Dutch real estate websites, such as Funda.nl.

<div align="center">
    <img src="./assets/images/app-example.jpg" >
</div>

## Key Features

- Queries for each website can be added with simple YAML files, including their scheduling.
- Notifications can be received through NTFY (app available on Android/iOS)
- Only new house offers will be notified. The ones that already have been notified won't repeat again.
- Deployment of the whole tool can be easily done with a docker compose file.

## Supported Websites

- Funda: https://www.funda.nl

> [!NOTE]
> Only Funda website is currently available for scraping. Other websites (e.g. of real estate brokers) will be supported on request (Github issue).

## App setup

1. Download the NTFY app from the [play store](https://play.google.com/store/apps/details?id=io.heckel.ntfy) (Android) or from the [app store](https://apps.apple.com/us/app/ntfy/id1625396347) (iOS)
2. Click on the plus icon to add a new topic. The default topic is `realty-alerts`. Using your own or creating a new topic is also possible. Just make the name unique to avoid that other people push to your topic, since all topics on the `https://ntfy.sh` server are public. If you wish, you can also use your own NTFY server url. For more info about this, check [here](https://docs.ntfy.sh/install/).

## How to Install

1. Check if docker is installed. If not, follow the guidelines in the [official website](https://docs.docker.com/engine/install/)
2. Copy the `docker-compose.yml` file from this repo
3. Create a `queries` folder. This will contain all the yml files with your preffered queries.
4. Inside the `queries` folder, create a new yml file. It's contents should look like this:

```yml
name: "Funda: 2521CC 5km radius"  # Name of the query. Good to keep it concise.
cron_schedule: "0 9,15 * * 1-5"  # A cron expression, for scheduling the query. Check https://crontab.guru for help.
query_url: https://www.funda.nl/zoeken/koop?selected_area=%5B%222521cc,10km%22%5D  # The query you're interested in.
max_listing_page_number: 3  # Optional. This is to avoid excessive scraping, which can result in website blocks.
notify_if_no_new_listing: false  # Optional.
```

5. If you want more queries, just create a new yml file and put it in the `queries` folder
6. Check if the `queries` folder is in the same location as the docker compose file (volumes) expects. If not, update the volume path in the docker compose file
7. Configure any environment variables in the docker compose file if needed. Please check [below](#additional-configuration)
8. Run the command:

```bash
docker compose up -d
```
9. Everything is set! If needed, check the logs (`docker compose logs`) to see if everything is working properly

## Additional configuration

Realty Alerts can be run as is, without any additional configuration. But in case needed, environment variables can be set. Here is a list of them and their default values:

| Env variable | Default value                 |
| ------------ | ----------------------------- |
| NTFY_URL     | https://ntfy.sh/realty-alerts |
| REDIS_URL    | redis://localhost:6379/0      |
| TIMEZONE     | Europe/Amsterdam              |

If using the standard `ntfy.sh` address, please change the topic (the `realty-alerts` part), to avoid sharing the same channel with other users.
