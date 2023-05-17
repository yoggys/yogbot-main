# Simple Pycord NASA API images module

![img](https://cdn.discordapp.com/attachments/927288026000945162/1108356297885229096/image.png)

## Installation

# Install the dependencies

```sh
pip install "aiohttp==3.8.4"
pip install "py-cord==2.4.1"
pip install "python-dotenv==1.0.0"
```

# Create a .env file and add NASA API key

```sh
NASA_API_KEY=...
```

# Add the module to your bot

```py
Bot.load_extension('cogs.Nasa')
```
