# ValenceCon

ValenceCon is a lightweight Kodi add-on that lets you browse and play media files directly from your Valence server within the Kodi interface. It can be thought of as a thin frontend for a Valence server.

ValenceCon can be used with Movie, TV Show, Anime, Music, Book, and Live TV libraries. It can easily switch between multiple profiles at will. It's easy to integrate with any customizable Kodi skin with a large collection of custom menus. Media items are populated from the server dynamically, and menu speed will vary based on local device speed.


## Installation

#### 1. Manual Installation

Download the latest release zip from the [ValenceCon releases](https://github.com/valenceOSS/valence/releases) and install via Kodi's "Install from zip file" option.

#### 2. First Run Setup

- Within a few seconds after installation, you will be prompted for your Valence server URL.
- Enter your Valence server address (e.g., `http://valence.local:8420` or `https://valence.example.com`)
- Select a profile from the list
- If the profile has a PIN, enter it when prompted

## Configuration

#### Configuring Home

Many Kodi skins allow for customizing of the home menu with custom nodes and widgets. Rather than a step by step guide, this section serves as an introduction to customizing a skin.

Examples:

If you would like a link on the home screen to open a library in your Valence server called "Kid's Movies", you would point the menu item to the path: Add-On -> Video Add-On -> ValenceCon -> Valence Libraries -> Kid's Movies -> Create menu item to here.

Beyond just modifying where the home menu headers go, many skins also allow you to use widgets. Widgets help populate the home screen with data, often the posters of media in the selected image. If you would like to display the most recent movies across all of your Valence libraries on the home screen, the path would be: Add-On -> Video Add-On -> ValenceCon -> Global Lists -> Movies -> Movies - Recently Added (20) -> Use as widget

Another common use case of widgets would be to display the next available episodes of shows that you may be watching:

    Add-On -> Video Add-On -> ValenceCon -> Valence Libraries -> Anime -> Anime - Next Up (20) -> Use as widget
    Add-On -> Video Add-On -> ValenceCon -> Global Lists -> TV Shows -> TV Shows - Next Up (20) -> Use as widget


## License

ValenceCon is licensed under the terms of the [MIT License](LICENSE.txt).