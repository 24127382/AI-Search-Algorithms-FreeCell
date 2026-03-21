from backend.engine.shuffle import deal_by_game_number, random_deal_number


def test_deal_by_game_number_accepts_any_integer_seed():
	negative_tableau = deal_by_game_number(-42)
	large_tableau = deal_by_game_number(10**18)

	assert len(negative_tableau) == 8
	assert len(large_tableau) == 8
	assert sum(len(column) for column in negative_tableau) == 52
	assert sum(len(column) for column in large_tableau) == 52


def test_random_deal_number_returns_integer_seed():
	random_seed = random_deal_number()
	assert isinstance(random_seed, int)
	assert random_seed >= 0
