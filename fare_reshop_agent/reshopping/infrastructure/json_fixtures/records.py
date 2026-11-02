from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, Strict, StrictBool, StrictInt, StrictStr

from fare_reshop_agent.reshopping.domain.trip import Cabin

type Amount = Annotated[Decimal, Strict()] | StrictInt


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MoneyRecord(Record):
    amount: Amount
    currency: StrictStr


class SegmentRecord(Record):
    origin: StrictStr
    destination: StrictStr
    departure: StrictStr
    arrival: StrictStr
    carrier: StrictStr
    flight_number: StrictStr = Field(alias="flightNumber")
    stops: StrictInt
    cabin: Cabin
    fare_basis: StrictStr = Field(alias="fareBasis")


class TicketRecord(Record):
    price_per_passenger: MoneyRecord = Field(alias="pricePerPassenger")
    total_paid: MoneyRecord = Field(alias="totalPaid")
    cabin: Cabin
    refundable: StrictBool
    change_fee_per_passenger: MoneyRecord = Field(alias="changeFeePerPassenger")
    baggage_included_pieces: StrictInt = Field(alias="baggageIncludedPieces")


class BookingRecord(Record):
    pnr: StrictStr
    passengers: StrictInt
    itinerary: tuple[SegmentRecord, ...]
    ticket: TicketRecord


class RouteRecord(Record):
    origin: StrictStr
    destination: StrictStr
    departure_date: StrictStr = Field(alias="departureDate")


class OfferRecord(Record):
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


# Reads only the identifier, so a bad record can still be reported under its own id;
# the full record models forbid unknown keys.
class BookingKey(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    pnr: Annotated[StrictStr, Field(min_length=1)]


class OfferKey(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    offer_id: Annotated[StrictStr, Field(min_length=1, alias="offerId")]


class BookingsFile(Record):
    comment: StrictStr | None = Field(default=None, alias="_comment")
    pnrs: tuple[object, ...]


class OffersFile(Record):
    comment: StrictStr | None = Field(default=None, alias="_comment")
    captured_at: StrictStr = Field(alias="capturedAt")
    offers: tuple[object, ...]
