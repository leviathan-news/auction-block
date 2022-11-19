# @version 0.4.0

"""
@title Mock Oracle
@notice Simple mock oracle for testing
"""

price: uint256


@deploy
def __init__(price: uint256):
    self.price = price


@external
@view
def price_oracle(index: uint256) -> uint256:
    return self.price


@external
def set_price(new_price: uint256):
    self.price = new_price


@external
@view
def feed_type() -> String[6]:
    return "ETHUSD"
