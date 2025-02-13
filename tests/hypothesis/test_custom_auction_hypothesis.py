import boa
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# Strategies for generating test parameters
# Explore various boundary and extreme scenarios for auction parameters
time_buffer_strategy = st.integers(min_value=0, max_value=2**256 - 1)
reserve_price_strategy = st.integers(min_value=0, max_value=2**256 - 1)
min_bid_increment_percentage_strategy = st.integers(min_value=0, max_value=100)
duration_strategy = st.integers(min_value=0, max_value=2**256 - 1)

@pytest.mark.skip()
def test_custom_auction_min_duration_constraint(auction_house):
    """
    Verify that auctions cannot be created with duration less than MIN_DURATION
    """
    owner = auction_house.owner()

    with boa.env.prank(owner):
        with pytest.raises(Exception) as excinfo:
            auction_house.create_custom_auction(
                3600,  # time_buffer
                10**18,  # reserve_price
                5,  # min_bid_increment_percentage
                3599,  # duration (just below 1 hour)
                "",  # ipfs_hash
            )
        assert "!duration" in str(excinfo.value)

@pytest.mark.skip()
def test_custom_auction_max_duration_constraint(auction_house):
    """
    Verify that auctions cannot be created with duration greater than MAX_DURATION
    """
    owner = auction_house.owner()

    with boa.env.prank(owner):
        with pytest.raises(Exception) as excinfo:
            auction_house.create_custom_auction(
                3600,  # time_buffer
                10**18,  # reserve_price
                5,  # min_bid_increment_percentage
                259201,  # duration (just above 3 days)
                "",  # ipfs_hash
            )
        assert "!duration" in str(excinfo.value)


@given(
    time_buffer=time_buffer_strategy,
    reserve_price=reserve_price_strategy,
    min_bid_increment=st.integers(min_value=2, max_value=15),  # Constrain to valid range
    duration=st.integers(min_value=3600, max_value=259200),  # Valid duration range
)
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=50
)
def test_custom_auction_parameter_generation(
    auction_house, time_buffer, reserve_price, min_bid_increment, duration
):
    """
    Hypothesis-based testing of custom auction parameter generation
    Explores various valid and potentially problematic parameter combinations
    """
    owner = auction_house.owner()

    # Test valid parameter ranges
    with boa.env.prank(owner):
        auction_id = auction_house.create_custom_auction(
            time_buffer, reserve_price, min_bid_increment, duration, ""  # ipfs_hash
        )

        # Verify auction was created with correct parameters
        auction = auction_house.auction_list(auction_id)

        # Index 7 contains the auction params tuple
        assert auction[7][0] == time_buffer
        assert auction[7][1] == reserve_price
        assert auction[7][2] == min_bid_increment
        assert auction[7][3] == duration

@pytest.mark.skip()
def test_min_bid_increment_percentage_constraints(auction_house):
    """
    Verify min bid increment percentage constraints
    """
    owner = auction_house.owner()

    # Test lower bound
    with boa.env.prank(owner):
        with pytest.raises(Exception) as excinfo:
            auction_house.create_custom_auction(
                3600,  # time_buffer
                10**18,  # reserve_price
                0,  # min_bid_increment_percentage (below minimum)
                3600,  # duration
                "",  # ipfs_hash
            )
        assert "!percentage" in str(excinfo.value)

    # Test upper bound
    with boa.env.prank(owner):
        with pytest.raises(Exception) as excinfo:
            auction_house.create_custom_auction(
                3600,  # time_buffer
                10**18,  # reserve_price
                1000,  # min_bid_increment_percentage (above maximum)
                3600,  # duration
                "",  # ipfs_hash
            )
        assert "!percentage" in str(excinfo.value)


@given(
    time_buffer=st.integers(min_value=0, max_value=2**256 - 1),
    reserve_price=st.integers(min_value=0, max_value=2**256 - 1),
    duration=st.integers(min_value=0, max_value=2**256 - 1),
)
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=50
)
def test_non_owner_custom_auction_prevention(
    auction_house, alice, time_buffer, reserve_price, duration
):
    """
    Verify that only the owner can create custom auctions
    """
    with boa.env.prank(alice):
        with pytest.raises(Exception):
            auction_house.create_custom_auction(
                time_buffer,
                reserve_price,
                5,  # min_bid_increment_percentage
                duration,
                "",  # ipfs_hash
            )


def test_extreme_parameter_scenarios(auction_house):
    """
    Test extreme and potentially problematic parameter scenarios
    """
    owner = auction_house.owner()

    # Scenarios to test:
    # 1. Zero time buffer
    # 2. Extremely high reserve price
    # 3. Minimal duration
    # 4. Zero reserve price
    test_scenarios = [
        {"name": "Zero Time Buffer", "params": [0, 10**18, 5, 3600, ""]},
        {"name": "Extremely High Reserve Price", "params": [3600, 2**256 - 1, 5, 3600, ""]},
        {"name": "Minimal Duration", "params": [3600, 10**18, 5, 3600, ""]},
        {"name": "Zero Reserve Price", "params": [3600, 0, 5, 3600, ""]},
    ]

    with boa.env.prank(owner):
        for scenario in test_scenarios:
            print(f"Testing scenario: {scenario['name']}")
            auction_id = auction_house.create_custom_auction(*scenario["params"])

            # Verify auction was created
            auction = auction_house.auction_list(auction_id)
            assert auction[0] == auction_id  # Verify auction ID
