import ee
import geemap
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional

# Initialize Google Earth Engine
ee.Initialize()

# Create FastAPI app
app = FastAPI(title="FloodSync API", description="API for flood mapping using Google Earth Engine")

# Load country boundaries
countries = ee.FeatureCollection("FAO/GAUL/2015/level0")

# Request model for flood map endpoint
class FloodMapRequest(BaseModel):
    country_name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    layer_type: str = "current"

@app.get("/countries")
async def get_countries():
    """Get list of available countries."""
    try:
        country_names = countries.aggregate_array("ADM0_NAME").distinct().sort().getInfo()
        return {"status": "success", "countries": country_names}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/flood_map")
async def generate_flood_map(request: FloodMapRequest):
    """Generate flood map for a specified country and date range."""
    try:
        # Validate inputs
        if not request.country_name:
            raise HTTPException(status_code=400, detail="Country name is required")
        
        # Set default dates if not provided
        current_date = datetime.now()
        start_date = request.start_date or (current_date - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = request.end_date or current_date.strftime("%Y-%m-%d")
        
        # Get country geometry
        country_geom = countries.filter(ee.Filter.eq("ADM0_NAME", request.country_name)).first().geometry()
        
        # Initialize result
        result = {
            "status": "success",
            "layer": request.layer_type,
            "geojson": None,
            "tile_url": None,
            "area_sqkm": None
        }
        
        if request.layer_type == "current":
            # Real-time flood mapping with Sentinel-1
            s1_collection = (ee.ImageCollection("COPERNICUS/S1_GRD")
                             .filterBounds(country_geom)
                             .filterDate(start_date, end_date)
                             .filter(ee.Filter.eq("instrumentMode", "IW"))
                             .select("VV"))
            latest_image = s1_collection.sort("system:time_start", False).first()
            water = latest_image.lt(-15).selfMask().clip(country_geom)
            
            # Convert to vector (GeoJSON)
            water_vector = water.reduceToVectors(
                geometry=country_geom,
                scale=30,
                geometryType="polygon",
                eightConnected=False,
                labelProperty="flood",
                reducer=ee.Reducer.countEvery()
            )
            geojson = geemap.ee_to_geojson(water_vector)
            
            # Generate map tile URL
            vis_params = {"palette": ["blue"]}
            tile_url = geemap.get_image_tile_url(water, vis_params)
            
            # Calculate flooded area
            area = water.multiply(ee.Image.pixelArea()).reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=country_geom,
                scale=30,
                maxPixels=1e10
            ).get("VV").getInfo() / 1e6  # Convert to sq.km
            
            result.update({
                "geojson": geojson,
                "tile_url": tile_url,
                "area_sqkm": area
            })
        
        elif request.layer_type == "historical":
            # Historical flood analysis with Landsat
            landsat = (ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
                       .filterBounds(country_geom)
                       .filterDate("2019-11-01", "2019-11-12")
                       .map(lambda image: image.normalizedDifference(["SR_B5", "SR_B3"]).rename("NDWI")))
            historical_ndwi = landsat.median()
            historical_flood = historical_ndwi.gt(0.3).selfMask().clip(country_geom)
            
            # Convert to vector (GeoJSON)
            flood_vector = historical_flood.reduceToVectors(
                geometry=country_geom,
                scale=30,
                geometryType="polygon",
                eightConnected=False,
                labelProperty="flood",
                reducer=ee.Reducer.countEvery()
            )
            geojson = geemap.ee_to_geojson(flood_vector)
            
            # Generate map tile URL
            vis_params = {"palette": ["cyan"]}
            tile_url = geemap.get_image_tile_url(historical_flood, vis_params)
            
            # Calculate flooded area
            area = historical_flood.multiply(ee.Image.pixelArea()).reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=country_geom,
                scale=30,
                maxPixels=1e10
            ).get("NDWI").getInfo() / 1e6  # Convert to sq.km
            
            result.update({
                "geojson": geojson,
                "tile_url": tile_url,
                "area_sqkm": area
            })
        
        elif request.layer_type == "risk":
            # Flood risk prediction with GPM rainfall
            rainfall_collection = (ee.ImageCollection("NASA/GPM_L3/IMERG_V06")
                                  .filterBounds(country_geom)
                                  .filterDate(start_date, end_date)
                                  .select("precipitationCal"))
            rainfall = rainfall_collection.mean()
            
            # Check if rainfall data exists
            if rainfall_collection.size().getInfo() > 0:
                high_rain = rainfall.gt(50)
                # Use historical flood for risk (simplified)
                landsat = (ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
                           .filterBounds(country_geom)
                           .filterDate("2019-11-01", "2019-11-12")
                           .map(lambda image: image.normalizedDifference(["SR_B5", "SR_B3"]).rename("NDWI")))
                historical_flood = landsat.median().gt(0.3)
                flood_risk = high_rain.And(historical_flood).selfMask().clip(country_geom)
                
                # Convert to vector (GeoJSON)
                risk_vector = flood_risk.reduceToVectors(
                    geometry=country_geom,
                    scale=30,
                    geometryType="polygon",
                    eightConnected=False,
                    labelProperty="risk",
                    reducer=ee.Reducer.countEvery()
                )
                geojson = geemap.ee_to_geojson(risk_vector)
                
                # Generate map tile URL
                vis_params = {"palette": ["red"]}
                tile_url = geemap.get_image_tile_url(flood_risk, vis_params)
                
                # Calculate risk area
                area = flood_risk.multiply(ee.Image.pixelArea()).reduceRegion(
                    reducer=ee.Reducer.sum(),
                    geometry=country_geom,
                    scale=30,
                    maxPixels=1e10
                ).get("NDWI").getInfo() / 1e6  # Convert to sq.km
                
                result.update({
                    "geojson": geojson,
                    "tile_url": tile_url,
                    "area_sqkm": area
                })
            else:
                result.update({
                    "status": "error",
                    "message": "No GPM rainfall data available for this period and area"
                })
        
        else:
            raise HTTPException(status_code=400, detail="Invalid layer_type. Use 'current', 'historical', or 'risk'")
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))