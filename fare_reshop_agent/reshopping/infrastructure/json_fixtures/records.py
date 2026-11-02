from decimal import Decimal
from typing import Annotated

from pydantic import Field, Strict, StrictBool, StrictInt, StrictStr

from fare_reshop_agent.reshopping.domain.trip import Cabin
from fare_reshop_agent.reshopping.infrastructure.file_problem import StrictRecord

type Amount = Annotated[Decimal, Strict()] | StrictInt


class MoneyRecord(StrictRecord):
    amount: Amount
    currency: StrictStr


class SegmentRecord(StrictRecord):
    origin: StrictStr
    destination: StrictStr
    departure: StrictStr
    arrival: StrictStr
    carrier: StrictStr
    flight_number: StrictStr = Field(alias="flightNumber")
    stops: StrictInt
    cabin: Cabin
    fare_basis: StrictStr = Field(alias="fareBasis")


class TicketRecord(StrictRecord):
    price_per_passenger: MoneyRecord = Field(alias="pricePerPassenger")
    total_paid: MoneyRecord = Field(alias="totalPaid")
    cabin: Cabin
    refundable: StrictBool
    change_fee_per_passenger: MoneyRecord = Field(alias="changeFeePerPassenger")
    baggage_included_pieces: StrictInt = Field(alias="baggageIncludedPieces")


class BookingRecord(StrictRecord):
    pnr: StrictStr
    passengers: StrictInt
    itinerary: tuple[SegmentRecord, ...]
    ticket: TicketRecord


class RouteRecord(StrictRecord):
    origin: StrictStr
    destination: StrictStr
    departure_date: StrictStr = Field(alias="departureDate")


class OfferRecord(StrictRecord):
    offer_id: StrictStr = Field(alias="offerId")
    route: RouteRecord
    carrier: StrictStr
    flight_number: StrictStr = Field(alias="flightNumber")
    departure: StrictStr
    arrival: StrictStr
    stops: StrictInt
    cabin: Cabin
    fare_basis: StrictStr = Field(alias="fareBasis")
    price: MoneyRecord
    refundable: StrictBool
    change_fee_per_passenger: MoneyRecord = Field(alias="changeFeePerPassenger")
    baggage_included_pieces: StrictInt = Field(alias="baggageIncludedPieces")
    seats_available: StrictInt = Field(alias="seatsAvailable")


class BookingsFile(StrictRecord):
    comment: StrictStr | None = Field(default=None, alias="_comment")
    pnrs: tuple[object, ...]


class OffersFile(StrictRecord):
    comment: StrictStr | None = Field(default=None, alias="_comment")
    captured_at: StrictStr = Field(alias="capturedAt")
    offers: tuple[object, ...]
