import ee
import geemap
ee.Initialize(project='fifth-catcher-456205-e8')
countries = ee.FeatureCollection("FAO/GAUL/2015/level0")
print(countries.aggregate_array("ADM0_NAME").distinct().sort().getInfo())