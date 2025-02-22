# @version 0.4.0

"""
@title Squid Price Oracle
@author https://github.com/leviathan-news/auction-block
@license MIT
@notice Indicative token price
@dev An artifact for frontend display, not robust enough for onchain usage!

                            ####++++++++
                       #+++++++++####+++##++
                     #########+++-++##++-..
                      ....++++#++++++#+++-....
                 ++++++----+++++++++++++++++-..-++##
                  ...-+++++++++++++++++++++++++++#####
              +++-....+#+++++++++++++++++++++++++######
          +++++++++++++++++++++++++++++++-+++++++++++++++++
        ++#########++++++++----+++--++----+++++++########++++
      ###############+++++-.-------------..+++++#############++
     ##########++++###++++.  .---------.  .+++++++++-+++  ######
     ########  ....--+++++.   .-------..  .++++++++++#+++#+ ####
    ########  ..--+++++++++....-------....+++++++####+++++## ###
     ######   +++++++++++++++-+-----+-++-+-++++++#######++++
     #####   +#######+#+++++++++-+-++-++++++++++++---+#####++
      ####  ++####+----+++++++++++++++++++++++++++++-  #####++
       ###  +###+.....-+++++++++++++++++++++++++###+++  +###++
            ++##+....-+++++#+++++++++++++#++++----+##++  +####+
            +###  ..-+#####++++++++++++++##+++-....##++   ####
            ++##   ++####+-++++##+##+++++++###++-+  +++  #####
             +##+  +####-..+++####++###++-.-+###+++ ++   ###
               +#  +####-..++#####--+###++--  +#++++
                   ++###   +++####+..-+###+++   ++++
                    ++#++   ++++###+     +#+++  +++
                     ++++     +++++++     +++++
                       +++      +++++++    +++
                                     ++    +
"""

# ============================================================================================
# 🧩 Interfaces
# ============================================================================================

interface Oracle:
    def price_oracle() -> uint256: view


interface OracleWithArguments:
    def price_oracle(k: uint256) -> uint256: view


# ============================================================================================
# 💾 Storage
# ============================================================================================

squid_eth_pool: public(Oracle)
eth_usd_pool: public(OracleWithArguments)


# ============================================================================================
# 🚧 Constructor
# ============================================================================================

@deploy
def __init__(squid_eth_pool: Oracle, eth_usd_pool: OracleWithArguments):
    self.squid_eth_pool = squid_eth_pool
    self.eth_usd_pool = eth_usd_pool


# ============================================================================================
# 👀 View functions
# ============================================================================================

@external
@view
def eth_price_usd() -> uint256:
    return staticcall self.eth_usd_pool.price_oracle(0)


@external
@view
def squid_price_eth() -> uint256:
    return staticcall self.squid_eth_pool.price_oracle()


@external
@view
def price_usd() -> uint256:
    """
    @notice Returns the USD price of the payment token
    @dev Uses the pool's price oracle (price in ETH terms) and the ETH/USD price oracle
         Both values are in 10**18 scale, so proper scaling is applied to avoid overflow
    @return Price of the payment token in USD (10**18 precision)
    """
    squid_price_eth: uint256 = staticcall self.squid_eth_pool.price_oracle()
    eth_price_usd: uint256 = staticcall self.eth_usd_pool.price_oracle(0)

    return (squid_price_eth * eth_price_usd) // 10**18
