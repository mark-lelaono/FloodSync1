#' Get available countries
#' @param api_url API base URL
#' @return List of country names
#' @export
get_countries <- function(api_url = "http://localhost:8000") {
  response <- httr::GET(paste0(api_url, "/countries"))
  jsonlite::fromJSON(httr::content(response, "text"))
}

#' Generate flood map
#' @param country Country name
#' @param start_date Start date (YYYY-MM-DD)
#' @param end_date End date (YYYY-MM-DD)
#' @param layer_type Layer type: "current", "historical", or "risk"
#' @param api_url API base URL
#' @return List containing flood map data (geojson, tile_url, area_sqkm)
#' @export
generate_flood_map <- function(country, start_date = NULL, end_date = NULL,
                               layer_type = "current", api_url = "http://localhost:8000") { # nolint: line_length_linter.
  response <- httr::POST(
    paste0(api_url, "/flood_map"),
    body = list(
      country_name = country,
      start_date = start_date,
      end_date = end_date,
      layer_type = layer_type
    ),
    encode = "json"
  )
  jsonlite::fromJSON(httr::content(response, "text"))
}    # nolint: trailing_whitespace_linter.