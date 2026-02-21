"""
AIQS Flight Search Service
WebSocket-based flight search with result parsing.
Ported from Django's FlightService.
"""
import json
import asyncio
import websockets
from app.config.settings import settings
from app.services.flight_auth_service import FlightAuthService


class FlightSearchService:
    """Handles AIQS WebSocket flight search and response parsing."""

    # ─── Build Search Request ───────────────────────────────────────────

    @staticmethod
    def build_search_request(params: dict) -> dict:
        """Build the AIQS FlightSearchRQ payload."""
        trip_type = params.get("tripType", "oneway")
        aiqs_trip = {"return": "R", "roundtrip": "R", "multicity": "M"}.get(trip_type, "O")

        ond_pairs = []

        if trip_type in ("return", "roundtrip"):
            ond_pairs = [
                {
                    "departureDate": params["departureDate"],
                    "originLocation": params["origin"],
                    "destinationLocation": params["destination"],
                },
                {
                    "departureDate": params.get("returnDate", ""),
                    "originLocation": params["destination"],
                    "destinationLocation": params["origin"],
                },
            ]
        elif trip_type == "multicity":
            segments = params.get("multiCitySegments", [])
            if segments:
                ond_pairs = [
                    {
                        "departureDate": seg.get("departureDate", ""),
                        "originLocation": seg.get("origin", ""),
                        "destinationLocation": seg.get("destination", ""),
                    }
                    for seg in segments
                ]
            else:
                ond_pairs = [
                    {
                        "departureDate": params["departureDate"],
                        "originLocation": params["origin"],
                        "destinationLocation": params["destination"],
                    }
                ]
        else:
            # One-way
            ond_pairs = [
                {
                    "departureDate": params["departureDate"],
                    "originLocation": params["origin"],
                    "destinationLocation": params["destination"],
                }
            ]

        adults = params.get("adults", 1)
        children = params.get("children", 0)
        infants = params.get("infants", 0)
        non_stop = params.get("nonStop", False)

        return {
            "service": "FlightRQ",
            "content": {
                "command": "FlightSearchRQ",
                "criteria": {
                    "criteriaType": "Air",
                    "commonRequestSearch": {
                        "numberOfUnits": adults + children + infants,
                        "typeOfUnit": "PX",
                        "resultsCount": str(params.get("maxResults", 50)),
                    },
                    "ondPairs": ond_pairs,
                    "preferredAirline": params.get("preferredAirlines", []),
                    "nonStop": non_stop,
                    "cabin": params.get("cabinClass", "Y"),
                    "maxStopQuantity": "Direct" if non_stop else "All",
                    "tripType": aiqs_trip,
                    "target": "Test",
                    "paxQuantity": {
                        "adt": adults,
                        "chd": children,
                        "inf": infants,
                    },
                },
            },
        }

    # ─── WebSocket Search ───────────────────────────────────────────────

    @classmethod
    async def search_flights(cls, search_params: dict) -> dict:
        """Authenticate, build request, run WS search, parse results."""
        tokens = await FlightAuthService.get_tokens()
        request = cls.build_search_request(search_params)
        raw_results = await cls._websocket_search(tokens["id_token"], request)
        return cls.parse_search_results(raw_results)

    @classmethod
    async def _websocket_search(cls, id_token: str, request: dict) -> list:
        """Connect to AIQS WebSocket and collect all response frames."""
        ws_url = f"{settings.AIQS_WSS_URL}/message"
        results = []

        request_with_token = {
            "request": {
                "service": request["service"],
                "token": id_token,
                "content": request["content"],
            }
        }

        try:
            async with websockets.connect(ws_url) as ws:
                await ws.send(json.dumps(request_with_token))

                timeout = 30
                start = asyncio.get_event_loop().time()

                while True:
                    try:
                        elapsed = asyncio.get_event_loop().time() - start
                        if elapsed > timeout:
                            break

                        response = await asyncio.wait_for(ws.recv(), timeout=10.0)
                        if not response or response.strip() == "":
                            continue

                        data = json.loads(response)
                        results.append(data)

                    except asyncio.TimeoutError:
                        break
                    except websockets.exceptions.ConnectionClosed:
                        break
                    except Exception:
                        break

        except Exception as e:
            raise Exception(f"Flight search failed: {e}")

        return results

    # ─── Parse Results ──────────────────────────────────────────────────

    @classmethod
    def parse_search_results(cls, results: list) -> dict:
        """Parse raw WS frames into structured flight data."""
        flights = []
        request_count = 0

        for result in results:
            if "requestDetails" in result:
                request_count = int(result["requestDetails"].get("count", 0))
                continue

            if "response" not in result:
                continue

            response = result["response"]
            if "content" not in response:
                continue

            content = response["content"]
            if "error" in content:
                continue

            # Capture searchKey from the response frame — needed for validate/fare-rules
            search_key = response.get("searchKey", "")

            search_resp = content.get("searchResponse", {})
            flight_index = search_resp.get("flightIndex", [])

            for flight in flight_index:
                # Inject searchKey into rawData so downstream endpoints can forward it
                flight["searchKey"] = search_key

                parsed = {
                    "id": flight.get("resultCount", {}).get("id"),
                    "refundable": flight.get("refundable", False),
                    "instantTicketing": flight.get("instantTicketing", False),
                    "bookOnHold": flight.get("bookOnHold", False),
                    "brandedFareSupported": flight.get("brandedFareSupported", False),
                    "fareRuleOffered": flight.get("fareRuleOffered", False),
                    "fare": {
                        "baseFare": float(flight.get("fare", {}).get("baseFare", 0)),
                        "tax": float(flight.get("fare", {}).get("tax", 0)),
                        "total": float(flight.get("fare", {}).get("total", 0)),
                        "currency": flight.get("fare", {}).get("currency", "PKR"),
                    },
                    "fareDetails": flight.get("fareDetails", {}),
                    "segments": cls._parse_segments(flight.get("ondPairs", [])),
                    "supplierCode": response.get("supplierCode"),
                    "supplierSpecific": flight.get("supplierSpecific"),
                    "brands": cls._parse_brands(flight.get("brands", [])),
                    "rawData": flight,
                }
                flights.append(parsed)

        return {
            "flights": flights,
            "total_count": len(flights),
            "request_count": request_count,
        }


    # ─── Segment Parsing ────────────────────────────────────────────────

    @classmethod
    def _parse_segments(cls, ond_pairs: list) -> list:
        segments = []
        for pair in ond_pairs:
            ond = pair.get("ond", {})
            flight_details = pair.get("flightDetails", [])

            segment = {
                "ond": {
                    "duration": ond.get("duration"),
                    "issuingAirline": ond.get("issuingAirline"),
                    "ondID": ond.get("ondID"),
                },
                "flights": [],
            }

            for fd in flight_details:
                flifo = fd.get("flifo", {})
                dt = flifo.get("dateTime", {})
                loc = flifo.get("location", {})
                company = flifo.get("companyId", {})
                baggage = flifo.get("baggageAllowance", [])

                segment["flights"].append({
                    "departureDate": dt.get("depDate"),
                    "departureTime": dt.get("depTime"),
                    "arrivalDate": dt.get("arrDate"),
                    "arrivalTime": dt.get("arrTime"),
                    "departureLocation": loc.get("depAirport"),
                    "departureTerminal": loc.get("depTerminal"),
                    "arrivalLocation": loc.get("arrAirport"),
                    "arrivalTerminal": loc.get("arrTerminal"),
                    "airlineCode": company.get("mktgAirline"),
                    "operatingAirline": company.get("operAirline"),
                    "flightNo": flifo.get("flightNo"),
                    "equipmentType": flifo.get("eqpType"),
                    "duration": flifo.get("duration"),
                    "cabin": flifo.get("cabin"),
                    "stops": int(flifo.get("stops", 0)),
                    "seatsAvailable": flifo.get("seatsAvlbl"),
                    "baggage": baggage,
                    "segID": fd.get("segID"),
                })

            segments.append(segment)

        return segments

    # ─── Brand Parsing ──────────────────────────────────────────────────

    @classmethod
    def _parse_brands(cls, brands: list) -> list:
        parsed = []
        for b in brands:
            parsed.append({
                "brandId": b.get("brandId"),
                "brandName": b.get("brandName"),
                "ondID": b.get("ondID"),
                "baseFare": float(b.get("baseFare", 0)),
                "tax": float(b.get("tax", 0)),
                "total": float(b.get("total", 0)),
                "currency": b.get("currency", "PKR"),
                "fareBreakup": b.get("fareBreakup", []),
                "inclusions": b.get("inclusions", {}),
                "supplierSpecific": b.get("supplierSpecific", {}),
            })
        return parsed
