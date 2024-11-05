# Dev branch only

If you wish to install the development version of the code from the Dev branch please follow the instructions below.

For Hass.io:
Install and configure SSH server from the "Add-on store". Once you have shell run the following:

```
mkdir -p /config/custom_components
cd /tmp/
git clone -b dev https://github.com/MindrustUK/Heatmiser-for-home-assistant /tmp/heatmiserneo
mv /tmp/heatmiserneo/custom_components/heatmiserneo /config/custom_components/
rm -rf /tmp/heatmiserneo/
```
