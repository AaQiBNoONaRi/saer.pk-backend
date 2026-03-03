"""
Flight Search Router
Endpoints for AIQS flight search, validation, fare rules, meals, branded fares, booking.
"""
import json
import asyncio
import httpx
import websockets
from fastapi import APIRouter, HTTPException, status
from app.config.settings import settings
from app.services.flight_auth_service import FlightAuthService
from app.services.flight_search_service import FlightSearchService
from app.schemas.flight_schemas import (
    FlightSearchRequest,
    FlightSearchResponse,
    FlightValidateRequest,
    FareRulesRequest,
    AncillaryRequest,
    FlightBookRequest,
    AuthTokenResponse,
)
from app.database.db_operations import db_ops
from datetime import datetime

router = APIRouter(prefix="/flight-search", tags=["Flight Search (AIQS)"])

# ─── Helpers ────────────────────────────────────────────────────────────────

def _get_supplier_specific(raw_supplier):
    """Normalize supplierSpecific to a list for endpoints that expect an array."""
    if isinstance(raw_supplier, list):
        return raw_supplier
    if isinstance(raw_supplier, dict):
        # Wrap the plain supplier dict directly — do NOT try to unwrap a nested key
        return [raw_supplier]
    return []


def _build_segment_group(ond_pairs: list, include_brand_id: bool = False) -> list:
    """Build AIQS segmentGroup from rawData ondPairs."""
    segment_group = []
    for pair in ond_pairs:
        ond_id = pair.get("ond", {}).get("ondID", 0)  # ondID lives on the ond object
        for fd in pair.get("flightDetails", []):
            flifo = fd.get("flifo", {})
            # Location fields can be either strings or objects like { trueLocationId: 'LHE' }
            loc = flifo.get("location", {}) or {}
            def _extract_airport(x):
                if not x:
                    return ''
                if isinstance(x, dict):
                    return x.get('trueLocationId') or x.get('locationId') or ''
                return x

            dep_airport = _extract_airport(loc.get('depAirport') or flifo.get('depAirport'))
            arr_airport = _extract_airport(loc.get('arrAirport') or flifo.get('arrAirport'))

            # company info may be in companyId or directly on location
            mktg = None
            oper = None
            issuing = None
            comp = flifo.get('companyId') or loc.get('companyId') or {}
            mktg = comp.get('mktgAirline') or loc.get('mktgAirline') or comp.get('marketing')
            oper = comp.get('operAirline') or loc.get('operAirline') or comp.get('operating')
            issuing = comp.get('issuingAirline') or loc.get('issuingAirline') or mktg

            seg = {
                "flifo": {
                    "dateTime": flifo.get("dateTime", {}),
                    "location": {
                        "depAirport": dep_airport,
                        "arrAirport": arr_airport,
                        **({} if not loc else {}),
                    },
                    "mktgAirline": mktg,
                    "operAirline": oper,
                    "issuingAirline": issuing,
                    "flightNo": flifo.get("flightNo") or fd.get('flightNo'),
                    "rbd": flifo.get("rbd"),
                    "flightTypeDetails": {
                        "ondID": ond_id,
                        "segID": fd.get("segID", 0),
                    },
                }
            }
            if include_brand_id:
                seg["brandId"] = None
            segment_group.append(seg)
    return segment_group



async def _ws_send_recv(ws_request: dict, timeout: int = 15) -> list:
    """Send a WS request (search only) and collect all JSON response frames."""
    ws_url = f"{settings.AIQS_WSS_URL}/message"
    results = []
    try:
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps(ws_request))
            start = asyncio.get_event_loop().time()
            while True:
                try:
                    elapsed = asyncio.get_event_loop().time() - start
                    if elapsed > timeout:
                        break
                    response = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    if response and response.strip():
                        try:
                            results.append(json.loads(response))
                        except json.JSONDecodeError:
                            pass
                except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                    break
    except Exception as e:
        raise Exception(f"WebSocket error: {e}")
    return results


async def _rest_post(path: str, payload: dict, id_token: str, timeout: int = 15) -> dict:
    """
    POST to the AIQS REST API.
    path example: '/api/air/getBrands'
    Returns the parsed JSON response dict.
    """
    import json as _json
    url = f"{settings.AIQS_REST_URL}{path}"
    headers = {
        "Authorization": f"Bearer {id_token}",
        "Content-Type": "application/json",
    }
    print(f"\n[REST] → POST {url}")
    print(f"[REST] → Payload: {_json.dumps(payload)[:800]}")
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload, headers=headers)
        print(f"[REST] ← Status: {resp.status_code}")
        if resp.status_code >= 400:
            try:
                err_body = resp.json()
            except Exception:
                err_body = resp.text
            print(f"[REST] ← Error body: {err_body}")
            raise Exception(f"AIQS REST {resp.status_code}: {err_body}")
        return resp.json()


# ─── 1. Auth ────────────────────────────────────────────────────────────────

@router.post("/auth", response_model=AuthTokenResponse)
async def get_auth_token():
    """Get or refresh AIQS authentication token."""
    try:
        tokens = await FlightAuthService.get_tokens()
        return {
            "access_token": tokens["access_token"],
            "id_token": tokens["id_token"],
            "expires_in": tokens["expires_in"],
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AIQS authentication failed: {str(e)}",
        )


# ─── 2. Flight Search ────────────────────────────────────────────────────────

@router.post("/search", response_model=FlightSearchResponse)
async def search_flights(req: FlightSearchRequest):
    """Search for flights via AIQS WebSocket. Returns parsed, normalized results."""
    try:
        result = await FlightSearchService.search_flights(req.model_dump())
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Flight search failed: {str(e)}",
        )


# ─── 3. Price Validation ─────────────────────────────────────────────────────

@router.post("/validate")
async def validate_flight(req: FlightValidateRequest):
    """
    Validate pricing for a selected flight via AIQS REST API (/api/air/validate).
    Returns sealed token, validatedFare and updated supplierSpecific needed for booking.
    """
    try:
        tokens = await FlightAuthService.get_tokens()
        id_token = tokens.get("id_token") or tokens.get("aiqs_token", "")
        raw = req.rawData
        fare = raw.get("fare", {})
        ond_pairs = raw.get("ondPairs", [])

        # Build segmentGroup with brandId: null (required by REST validate API)
        segment_group = _build_segment_group(ond_pairs, include_brand_id=True)

        # Resolve from/to airports
        from_airport = ""
        to_airport = ""
        if ond_pairs:
            def _maybe_extract_airport(obj):
                if not obj:
                    return ''
                if isinstance(obj, dict):
                    return obj.get('trueLocationId') or obj.get('depAirport') or obj.get('locationId') or ''
                return obj

            first_fd = ond_pairs[0].get("flightDetails", [{}])[0].get("flifo", {})
            last_fd = ond_pairs[-1].get("flightDetails", [{}])[-1].get("flifo", {})
            from_airport = _maybe_extract_airport(first_fd.get('location') or first_fd.get('depAirport'))
            to_airport = _maybe_extract_airport(last_fd.get('location') or last_fd.get('arrAirport'))

        supplier_specific = _get_supplier_specific(req.supplierSpecific)

        # Use explicit pax/tripType/searchKey from request (passed from frontend search params)
        # Fall back to rawData if not provided (backwards compat)
        search_key = req.searchKey or raw.get("searchKey", "")
        trip_type = req.tripType or raw.get("tripType", "O")
        adt = req.adt if req.adt else raw.get("paxQuantity", {}).get("adt", 1)
        chd = req.chd if req.chd else raw.get("paxQuantity", {}).get("chd", 0)
        inf = req.inf if req.inf else raw.get("paxQuantity", {}).get("inf", 0)

        rest_payload = {
            "request": {
                "service": "FlightRQ",
                "supplierCodes": [int(req.supplierCode) if req.supplierCode else 2],
                "node": {"agencyCode": "CLI_11078"},
                "searchKey": search_key,
                "content": {
                    "command": "FlightValidateRQ",
                    "validateFareRequest": {
                        "totalAmount": float(fare.get("total", 0)),
                        "target": "Test",
                        "adt": adt,
                        "chd": chd,
                        "inf": inf,
                        "segmentGroup": segment_group,
                        "tripType": trip_type,
                        "from": from_airport,
                        "to": to_airport,
                    },
                    "supplierSpecific": supplier_specific,
                },
                "selectCredential": {"id": 33, "officeIdList": [{"id": 24}]},
                "token": id_token,
            }
        }

        import json as _json
        print(f"\n[VALIDATE] → REST payload: {_json.dumps(rest_payload)[:1200]}")
        result = await _rest_post("/api/air/validate", rest_payload, id_token, timeout=45)
        print(f"[VALIDATE] ← response keys: {list(result.keys()) if result else 'empty'}")

        # Parse the REST response: response.content.validateFareResponse
        content = result.get("response", {}).get("content", {})
        validate_rs = content.get("validateFareResponse", {})
        updated_supplier_specific = content.get("supplierSpecific", {})

        sealed = validate_rs.get("sealed")
        validated_fare = validate_rs.get("fare")

        return {
            "status": "validated",
            "sealed": sealed,
            "validatedFare": validated_fare,
            # Return updated supplierSpecific so frontend can use Book_fareSessionId for booking
            "supplierSpecific": updated_supplier_specific,
            "raw": result,
        }

    except Exception as e:
        import traceback
        print(f"[VALIDATE] ✗ Error: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Price validation failed: {str(e)}",
        )


# ─── 4. Fare Rules ───────────────────────────────────────────────────────────

@router.post("/fare-rules")
async def get_fare_rules(req: FareRulesRequest):
    """Fetch fare rules via AIQS REST API (FlightFareruleRQ)."""
    try:
        tokens = await FlightAuthService.get_tokens()
        id_token = tokens.get("id_token") or tokens.get("aiqs_token", "")
        raw = req.rawData or {}
        ond_pairs = raw.get("ondPairs", [])
        segment_group = _build_segment_group(ond_pairs, include_brand_id=True)

        # Get from/to airports
        from_airport = ""
        to_airport = ""
        if ond_pairs:
            from_airport = ond_pairs[0].get("flightDetails", [{}])[0].get("flifo", {}).get("location", {}).get("depAirport", "")
            to_airport = ond_pairs[-1].get("flightDetails", [{}])[-1].get("flifo", {}).get("location", {}).get("arrAirport", "")

        # supplierSpecific must be a list
        supplier_specific = _get_supplier_specific(req.supplierSpecific)

        rest_payload = {
            "request": {
                "service": "FlightRQ",
                "supplierCodes": [int(req.supplierCode) if req.supplierCode else 2],
                "node": {"agencyCode": "CLI_11078"},
                "content": {
                    "command": "FlightFareruleRQ",
                    "fareRuleRequest": {
                        "totalAmount": getattr(req, "totalAmount", None),
                        "target": "Test",
                        "adt": raw.get("paxQuantity", {}).get("adt", 1),
                        "chd": raw.get("paxQuantity", {}).get("chd", 0),
                        "inf": raw.get("paxQuantity", {}).get("inf", 0),
                        "segmentGroup": segment_group,
                        "tripType": raw.get("tripType", "O"),
                        "from": from_airport,
                        "to": to_airport,
                    },
                    "supplierSpecific": supplier_specific,
                },
                "selectCredential": {"id": 33, "officeIdList": [{"id": 24}]},
            }
        }

        result = await _rest_post("/api/air/farerule", rest_payload, id_token)
        content = result.get("response", {}).get("content", {})
        fare_rule_rs = content.get("fareRuleResponse", {})
        air_fare_rule = fare_rule_rs.get("airFareRule", [])
        return {"fareRules": air_fare_rule, "raw": result}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Fare rules fetch failed: {str(e)}",
        )


# ─── 5. Branded Fares (REST POST) ───────────────────────────────────────────

@router.post("/branded-fares")
async def get_branded_fares(req: AncillaryRequest):
    """
    Fetch branded fare options via AIQS REST API (FlightBrandRQ).
    Requires rawData + supplierSpecific from the selected flight.
    """
    try:
        tokens = await FlightAuthService.get_tokens()
        id_token = tokens.get("id_token") or tokens.get("aiqs_token", "")
        raw = req.rawData or {}
        ond_pairs = raw.get("ondPairs", [])
        # include_brand_id=False — no brandId field in segments for getBrands
        segment_group = _build_segment_group(ond_pairs, include_brand_id=False)

        # supplierSpecific must be a plain object (not array) for FlightBrandRQ
        raw_supplier = req.supplierSpecific
        if isinstance(raw_supplier, list):
            supplier_specific = raw_supplier[0] if raw_supplier else {}
        elif isinstance(raw_supplier, dict):
            supplier_specific = raw_supplier
        else:
            supplier_specific = {}

        rest_payload = {
            "request": {
                "service": "FlightRQ",
                "supplierCodes": [int(req.supplierCode) if req.supplierCode else 2],
                "node": {"agencyCode": "CLI_11078"},
                "content": {
                    "command": "FlightBrandRQ",
                    "brandRequest": {
                        "totalAmount": None,
                        "target": "Test",
                        "adt": raw.get("paxQuantity", {}).get("adt", 1),
                        "chd": raw.get("paxQuantity", {}).get("chd", 0),
                        "inf": raw.get("paxQuantity", {}).get("inf", 0),
                        "segmentGroup": segment_group,
                        "tripType": raw.get("tripType", "O"),
                    },
                    "supplierSpecific": supplier_specific,
                },
                "selectCredential": {"id": 33, "officeIdList": [{"id": 24}]},
            }
        }

        result = await _rest_post("/api/air/getBrands", rest_payload, id_token)

        # Extract brands from response
        content = result.get("response", {}).get("content", {})
        brand_rs = content.get("brandResponse", content.get("brandedFareResponse", {}))
        brands = brand_rs.get("brands", brand_rs.get("brandedFares", [])) if brand_rs else []

        return {"brands": brands, "raw": result}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Branded fares fetch failed: {str(e)}",
        )


# ─── 6. Meals Ancillary (WebSocket POST) ────────────────────────────────────

@router.post("/meals")
async def get_meals(req: AncillaryRequest):
    """
    Fetch available meal options via AIQS REST API (FlightMealAncillaryRQ).
    Requires rawData + supplierSpecific from the selected flight.
    """
    try:
        tokens = await FlightAuthService.get_tokens()
        id_token = tokens.get("id_token") or tokens.get("aiqs_token", "")
        raw = req.rawData or {}
        ond_pairs = raw.get("ondPairs", [])
        segment_group = _build_segment_group(ond_pairs)

        # supplierSpecific must be a plain object (not array) for ancillary endpoints
        raw_ss = req.supplierSpecific
        if isinstance(raw_ss, list):
            supplier_specific = raw_ss[0] if raw_ss else {}
        elif isinstance(raw_ss, dict):
            supplier_specific = raw_ss
        else:
            supplier_specific = {}

        rest_payload = {
            "request": {
                "service": "FlightRQ",
                "supplierCodes": [int(req.supplierCode) if req.supplierCode else 2],
                "node": {"agencyCode": "CLI_11078"},
                "content": {
                    "command": "FlightMealAncillaryRQ",
                    "flightMealRequest": {
                        "adt": raw.get("paxQuantity", {}).get("adt", 1),
                        "chd": raw.get("paxQuantity", {}).get("chd", 0),
                        "inf": raw.get("paxQuantity", {}).get("inf", 0),
                        "segmentGroup": segment_group,
                    },
                    "supplierSpecific": supplier_specific,
                },
                "selectCredential": {"id": 167},
            }
        }

        import json as _json
        print(f"\n[MEALS] → supplier={req.supplierCode} supplierSpecific type={type(supplier_specific).__name__}")
        print(f"[MEALS] → payload: {_json.dumps(rest_payload)[:1000]}")
        try:
            result = await _rest_post("/api/air/getMeal", rest_payload, id_token, timeout=20)
        except Exception as rest_err:
            # Many airlines don't support meal ancillaries — return empty gracefully
            print(f"[MEALS] ⚠ API returned error (likely not supported for this airline): {rest_err}")
            return {"meals": [], "supported": False, "message": "Meal ancillaries not available for this flight."}

        content = result.get("response", {}).get("content", {})
        meal_rs = content.get("mealResponse", content.get("flightMealResponse", []))
        meals = meal_rs if isinstance(meal_rs, list) else []

        return {"meals": meals, "raw": result, "supported": True}

    except Exception as e:
        import traceback
        print(f"[MEALS] ✗ Error: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Meals fetch failed: {str(e)}",
        )


# ─── 7. Baggage Ancillary (WebSocket POST) ──────────────────────────────────

@router.post("/baggage")
async def get_baggage(req: AncillaryRequest):
    """
    Fetch extra baggage options via AIQS REST API (FlightBaggageAncillaryRQ).
    Requires rawData + supplierSpecific from the selected flight.
    """
    try:
        tokens = await FlightAuthService.get_tokens()
        id_token = tokens.get("id_token") or tokens.get("aiqs_token", "")
        raw = req.rawData or {}
        ond_pairs = raw.get("ondPairs", [])
        segment_group = _build_segment_group(ond_pairs)
        supplier_specific = _get_supplier_specific(req.supplierSpecific)

        rest_payload = {
            "request": {
                "service": "FlightRQ",
                "supplierCodes": [int(req.supplierCode) if req.supplierCode else 2],
                "node": {"agencyCode": "CLI_11078"},
                "content": {
                    "command": "FlightBaggageAncillaryRQ",
                    "flightBaggageRequest": {
                        "adt": raw.get("paxQuantity", {}).get("adt", 1),
                        "chd": raw.get("paxQuantity", {}).get("chd", 0),
                        "inf": raw.get("paxQuantity", {}).get("inf", 0),
                        "segmentGroup": segment_group,
                    },
                    "supplierSpecific": supplier_specific,
                },
                "selectCredential": {"id": 167},
            }
        }

        import json as _json
        print(f"\n[BAGGAGE] → supplier={req.supplierCode}")
        print(f"[BAGGAGE] → payload: {_json.dumps(rest_payload)[:1000]}")
        try:
            result = await _rest_post("/api/air/getBaggage", rest_payload, id_token, timeout=20)
        except Exception as rest_err:
            print(f"[BAGGAGE] ⚠ API returned error (likely not supported for this airline): {rest_err}")
            return {"baggage": [], "supported": False, "message": "Extra baggage ancillaries not available for this flight."}

        content = result.get("response", {}).get("content", {})
        bag_rs = content.get("baggageResponse", content.get("flightBaggageResponse", []))
        baggage = bag_rs if isinstance(bag_rs, list) else []

        return {"baggage": baggage, "raw": result, "supported": True}

    except Exception as e:
        import traceback
        print(f"[BAGGAGE] ✗ Error: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Baggage fetch failed: {str(e)}",
        )


# ─── 8. Book Flight (Create PNR) ─────────────────────────────────────────────

@router.post("/book")
async def book_flight(req: FlightBookRequest):
    """
    Create a PNR via AIQS REST API (/api/air/book — FlightBookRQ).
    Requires validated supplierSpecific (from /validate response) + passenger data.
    """
    try:
        tokens = await FlightAuthService.get_tokens()
        id_token = tokens.get("id_token") or tokens.get("aiqs_token", "")
        raw = req.rawData or {}
        fare = raw.get("fare", {})
        ond_pairs_raw = raw.get("ondPairs", [])

        # ── Date format helper: YYYY-MM-DD → DD-MM-YYYY ─────────────────
        def fmt_date(d: str) -> str:
            """Convert ISO date YYYY-MM-DD from HTML inputs to AIQS format DD-MM-YYYY."""
            if not d:
                return ""
            parts = d.split("-")
            if len(parts) == 3 and len(parts[0]) == 4:
                return f"{parts[2]}-{parts[1]}-{parts[0]}"
            return d  # already DD-MM-YYYY or unknown format

        # ── Build travelerInfo ────────────────────────────────────────────
        traveler_info = []
        for pax in req.passengers:
            traveler = {
                "paxType": pax.get("paxType", "ADT"),
                "gender": pax.get("gender", "Male"),
                "salutation": pax.get("salutation", "Mr"),
                "givenName": pax.get("givenName", "").upper(),
                "surName": pax.get("surName", "").upper(),
                "birthDate": fmt_date(pax.get("birthDate", "")),
                # docType as string "1" per AIQS spec (not "P")
                "docType": str(pax.get("docType", "1")),
                "docID": pax.get("docID", ""),
                "docIssueCountry": pax.get("docIssueCountry", "PK"),
                "expiryDate": fmt_date(pax.get("expiryDate", "")),
                "nationality": pax.get("nationality", "PK"),
                "contact": {
                    "phoneList": [
                        {
                            "number": pax.get("phone", ""),
                            "phoneType": {"id": 1},
                            "country": {
                                "code": pax.get("countryCode", "PK"),
                                "telephonecode": pax.get("phoneCode", "92"),
                            },
                        }
                    ],
                    "emailList": [
                        {
                            "emailId": pax.get("email", ""),
                            "emailType": {"id": 1},
                        }
                    ],
                },
            }
            traveler_info.append(traveler)

        # ── Build ondPairs in AIQS book format ────────────────────────────
        # AIQS expects: [{duration, originCity, destinationCity, ondID, segments:[{segID, depDate, ...}]}]
        ond_pairs_book = []
        for pair in ond_pairs_raw:
            ond = pair.get("ond", {})
            segments_book = []
            for fd in pair.get("flightDetails", []):
                flifo = fd.get("flifo", {})
                dt = flifo.get("dateTime", {})
                loc = flifo.get("location", {})
                company = flifo.get("companyId", {})
                baggage = flifo.get("baggageAllowance", [])
                segments_book.append({
                    "segID": fd.get("segID", 0),
                    "depDate": dt.get("depDate", ""),
                    "depTime": dt.get("depTime", ""),
                    "arrDate": dt.get("arrDate", ""),
                    "arrTime": dt.get("arrTime", ""),
                    "depAirport": loc.get("depAirport", ""),
                    "arrAirport": loc.get("arrAirport", ""),
                    "depTerminal": loc.get("depTerminal", ""),
                    "arrTerminal": loc.get("arrTerminal", ""),
                    "mktgAirline": company.get("mktgAirline", ""),
                    "operAirline": company.get("operAirline", ""),
                    "issuingAirline": company.get("mktgAirline", ""),
                    "flightNo": flifo.get("flightNo", ""),
                    "cabin": flifo.get("cabin", "Y"),
                    "rbd": flifo.get("rbd", ""),
                    "eqpType": flifo.get("eqpType", ""),
                    "stopQuantity": flifo.get("stops", 0),
                    "baggageAllowance": baggage,
                })
            ond_pairs_book.append({
                "duration": ond.get("duration", ""),
                "originCity": ond_pairs_raw[0].get("flightDetails", [{}])[0]
                              .get("flifo", {}).get("location", {}).get("depAirport", ""),
                "destinationCity": ond_pairs_raw[-1].get("flightDetails", [{}])[-1]
                                   .get("flifo", {}).get("location", {}).get("arrAirport", ""),
                "ondID": ond.get("ondID", 0),
                "segments": segments_book,
            })

        # ── supplierSpecific for content: use validatedSupplierSpecific from /validate ──
        # AIQS expects supplierSpecific as an array [{}]. Wrap via helper to ensure this.
        content_supplier_specific = _get_supplier_specific(
            req.validatedSupplierSpecific or req.supplierSpecific
        )

        # Use supplierCode from request (may differ per airline/supplier)
        supplier_code = int(req.supplierCode) if req.supplierCode else 2

        # For book endpoint AIQS expects supplierSpecific as a plain object (not array)
        # Unwrap from list if _get_supplier_specific returned one
        raw_ss = req.validatedSupplierSpecific or req.supplierSpecific
        if isinstance(raw_ss, list):
            content_supplier_specific = raw_ss[0] if raw_ss else {}
        else:
            content_supplier_specific = raw_ss or {}

        # ── Build booking payload (matches AIQS FlightBookRQ spec exactly) ──────
        rest_payload = {
            "request": {
                "service": "FlightRQ",
                "content": {
                    "command": "FlightBookRQ",
                    # supplierSpecific is a plain object for book (not an array)
                    "supplierSpecific": content_supplier_specific,
                    "bookFlightRQ": {
                        "tripType": req.tripType or raw.get("tripType", "O"),
                        "adt": req.adt,
                        "chd": req.chd,
                        "inf": req.inf,
                        "travelerInfo": traveler_info,
                        "ondPairs": ond_pairs_book,
                        "fare": fare,
                        "airFareRule": raw.get("airFareRule", []),
                        "miniRules": [],
                        # sealed token from /validate response belongs here
                        "sealed": req.sealed or None,
                        # extra fields seen in AIQS working payloads
                        "issue": False,
                        "paymentCard": None,
                        "paymentMode": None,
                        "bookingRefId": None,
                    },
                },
                "node": {"agencyCode": "CLI_11078"},
                "selectCredential": {"id": 33, "officeIdList": [{"id": 24}]},
                "supplierCodes": [supplier_code],
                # NOTE: no top-level 'token' field — auth is via Book_fareSessionId
            }
        }

        import json as _json
        print(f"\n[BOOK] → REST payload: {_json.dumps(rest_payload)[:2000]}")
        result = await _rest_post("/api/air/book", rest_payload, id_token, timeout=60)

        # Log full response to diagnose parsing
        print(f"[BOOK] ← FULL response: {_json.dumps(result)[:3000]}")

        # ── Parse booking response ────────────────────────────────────────
        resp_content = result.get("response", {}).get("content", {})
        print(f"[BOOK] ← content keys: {list(resp_content.keys()) if resp_content else 'empty'}")

        # AIQS returns bookFlightResult (not bookFlightRS)
        book_rs = (
            resp_content.get("bookFlightResult")
            or resp_content.get("bookFlightRS")
            or resp_content.get("bookingRS")
            or {}
        )
        print(f"[BOOK] ← book_rs keys: {list(book_rs.keys()) if book_rs else 'empty'}")

        pnr = book_rs.get("pnr")
        booking_ref_id = book_rs.get("bookingRefId")
        # airlineLocator is inside airlineReservation[0]
        reservations = book_rs.get("airlineReservation", [])
        airline_locator = reservations[0].get("airlineLocator") if reservations else None
        airline_code = reservations[0].get("airlineCode") if reservations else None
        booking_fare = book_rs.get("fare")
        booking_status = book_rs.get("status", "HK")

        print(f"[BOOK] ← parsed: pnr={pnr}, refId={booking_ref_id}, status={booking_status}")

        # ── Save booking to MongoDB ─────────────────────────────────────────
        booking_doc = {
            "pnr": pnr,
            "bookingRefId": booking_ref_id,
            "airlineLocator": airline_locator,
            "airlineCode": airline_code,
            "status": booking_status,
            "tripType": req.tripType or raw.get("tripType", "O"),
            "adt": req.adt,
            "chd": req.chd,
            "inf": req.inf,
            "supplierCode": supplier_code,
            "bookedAt": datetime.utcnow().isoformat(),
        }
        try:
            await db_ops.create("flight_bookings", booking_doc)
            print(f"[BOOK] ✓ Saved booking {booking_ref_id} to DB")
        except Exception as db_err:
            print(f"[BOOK] ⚠ DB save failed (booking still succeeded): {db_err}")

        return {
            "status": booking_status,
            "pnr": pnr,
            "bookingRefId": booking_ref_id,
            "airlineLocator": airline_locator,
            "airlineCode": airline_code,
            "fare": booking_fare,
            "raw": result,
        }

    except Exception as e:
        import traceback
        print(f"[BOOK] ✗ Error: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Flight booking failed: {str(e)}",
        )


# ─── List Saved Bookings ──────────────────────────────────────────────────────
@router.get("/bookings")
async def list_bookings(skip: int = 0, limit: int = 50):
    """Return all flight bookings saved in the database."""
    docs = await db_ops.get_all("flight_bookings", skip=skip, limit=limit)
    # Serialize ObjectId to string
    for d in docs:
        d["_id"] = str(d.get("_id", ""))
    # Newest first
    docs.sort(key=lambda d: d.get("bookedAt", ""), reverse=True)
    return {"bookings": docs, "total": len(docs)}


# ─── Retrieve PNR Detail from AIQS ───────────────────────────────────────────
from pydantic import BaseModel as _BM

class RetrieveBookingRequest(_BM):
    bookingRefId: str
    supplierCode: int = 2

@router.post("/booking-detail")
async def retrieve_booking_detail(req: RetrieveBookingRequest):
    """Fetch full PNR details from AIQS using FlightRetrieveBookingRQ."""
    try:
        tokens = await FlightAuthService.get_tokens()
        id_token = tokens["id_token"]

        payload = {
            "request": {
                "service": "FlightRQ",
                "content": {
                    "command": "FlightRetrieveBookingRQ",
                    "tripDetailRQ": {
                        "bookingRefId": req.bookingRefId,
                    },
                    "supplierSpecific": None,
                },
                "node": {"agencyCode": "CLI_11078"},
                "selectCredential": {
                    "id": 33,
                    "officeIdList": [{
                        "id": 24,
                        "officeId": None,
                        "currency": None,
                        "fop": None,
                        "bspCardDetails": None,
                        "otherConfiguration": None,
                        "mvelRule": None,
                        "privileges": None,
                        "bookingPcc": None,
                    }]
                },
                "supplierCodes": [req.supplierCode]
            }
        }

        print(f"[RETRIEVE] → bookingRefId={req.bookingRefId}")
        # Correct AIQS endpoint for PNR retrieval
        result = await _rest_post("/api/air/retrievePNR", payload, id_token, timeout=30)
        content = result.get("response", {}).get("content", {})
        print(f"[RETRIEVE] ← content keys: {list(content.keys())}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[RETRIEVE] ✗ Error: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Booking detail fetch failed: {str(e)}",
        )


# ─── Update Passport ──────────────────────────────────────────────────────────

class UpdatePassportRequest(_BM):
    bookingRefId: str
    supplierCode: int = 2
    supplierSpecific: dict  # passed from frontend (segRef, availabilitySourceMap, etc.)
    travelerInfo: list  # list of passenger dicts as per AIQS spec


@router.post("/update-passport")
async def update_passport(req: UpdatePassportRequest):
    """Update passport/traveler details for an existing PNR using FlightUpdatePassportRQ."""
    try:
        tokens = await FlightAuthService.get_tokens()
        id_token = tokens["id_token"]

        payload = {
            "request": {
                "service": "FlightRQ",
                "content": {
                    "command": "FlightUpdatePassportRQ",
                    "supplierSpecific": req.supplierSpecific,
                    "updatePnrRQ": {
                        "bookingRefId": req.bookingRefId,
                        "travelerInfo": req.travelerInfo,
                    },
                },
                "node": {"agencyCode": "CLI_11078"},
                "selectCredential": {
                    "id": 33,
                    "officeIdList": [{"id": 24}],
                },
                "supplierCodes": [req.supplierCode],
            }
        }

        print(f"[UPDATE-PASSPORT] → bookingRefId={req.bookingRefId}, pax={len(req.travelerInfo)}")
        result = await _rest_post("/api/air/book", payload, id_token, timeout=30)
        content = result.get("response", {}).get("content", {})
        print(f"[UPDATE-PASSPORT] ← content keys: {list(content.keys())}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[UPDATE-PASSPORT] ✗ Error: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Update passport failed: {str(e)}",
        )
