from pydantic import BaseModel


class Country(BaseModel):
    code: str
    name: str
    currency: str


COUNTRIES = [
    Country(code="SG", name="Singapore", currency="SGD"),
    Country(code="MY", name="Malaysia", currency="MYR"),
    Country(code="PH", name="Philippines", currency="PHP"),
    Country(code="ID", name="Indonesia", currency="IDR"),
    Country(code="TH", name="Thailand", currency="THB"),
    Country(code="HK", name="Hong Kong", currency="HKD"),
    Country(code="TW", name="Taiwan", currency="TWD"),
    Country(code="JP", name="Japan", currency="JPY"),
    Country(code="KR", name="South Korea", currency="KRW"),
    Country(code="IN", name="India", currency="INR"),
    Country(code="AU", name="Australia", currency="AUD"),
    Country(code="NZ", name="New Zealand", currency="NZD"),
    Country(code="US", name="United States", currency="USD"),
    Country(code="CA", name="Canada", currency="CAD"),
    Country(code="GB", name="United Kingdom", currency="GBP"),
    Country(code="DE", name="Germany", currency="EUR"),
    Country(code="FR", name="France", currency="EUR"),
]

BY_CODE = {c.code: c for c in COUNTRIES}
