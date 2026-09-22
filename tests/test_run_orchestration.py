from call_runner import CallOutcome, SipDialError, run_call


class FakeClock:
    def __init__(self):
        self.time = 0.0

    def now(self) -> float:
        return self.time

    async def sleep(self, seconds: float) -> None:
        self.time += seconds


class FakeClient:
    def __init__(self, active_sequence, agent_ready=True):
        # active_sequence: list of bools consumed on each is_sip_participant_active
        # call; the last value repeats once exhausted.
        self._active_sequence = list(active_sequence)
        self.agent_ready = agent_ready
        self.calls = []
        self.created_rooms = []
        self.deleted_rooms = []
        self.dispatched = []
        self.dial_error: Exception | None = None

    async def create_room(self, name):
        self.calls.append(("create_room", name))
        self.created_rooms.append(name)

    async def dispatch_agent(self, room_name, scenario_path):
        self.calls.append(("dispatch_agent", room_name, scenario_path))
        self.dispatched.append((room_name, scenario_path))

    async def wait_for_agent_ready(self, room_name, timeout):
        self.calls.append(("wait_for_agent_ready", room_name))
        return self.agent_ready

    async def create_sip_participant(self, room_name, phone_number, trunk_id):
        self.calls.append(("create_sip_participant", room_name, phone_number, trunk_id))
        if self.dial_error:
            raise self.dial_error

    async def is_sip_participant_active(self, room_name):
        self.calls.append(("is_sip_participant_active", room_name))
        if len(self._active_sequence) > 1:
            return self._active_sequence.pop(0)
        return self._active_sequence[0]

    async def delete_room(self, room_name):
        self.calls.append(("delete_room", room_name))
        self.deleted_rooms.append(room_name)


async def test_successful_call_completes_when_sip_participant_leaves():
    clock = FakeClock()
    # answered immediately (True), stays active for a couple polls, then leaves (False)
    client = FakeClient(active_sequence=[True, True, True, False])

    result = await run_call(
        client,
        scenario_slug="simple_scheduling_1",
        room_name="room-1",
        scenario_path="scenarios/simple_scheduling_1.yaml",
        phone_number="+18054398008",
        trunk_id="ST_abc",
        max_seconds=240,
        poll_interval=1.0,
        sleep_fn=clock.sleep,
        now_fn=clock.now,
    )

    assert result.outcome == CallOutcome.COMPLETED
    assert client.deleted_rooms == ["room-1"]
    assert client.dispatched == [("room-1", "scenarios/simple_scheduling_1.yaml")]
    assert ("create_sip_participant", "room-1", "+18054398008", "ST_abc") in client.calls


async def test_no_answer_when_sip_participant_never_becomes_active():
    clock = FakeClock()
    client = FakeClient(active_sequence=[False])

    result = await run_call(
        client,
        scenario_slug="simple_scheduling_1",
        room_name="room-2",
        scenario_path="scenarios/simple_scheduling_1.yaml",
        phone_number="+18054398008",
        trunk_id="ST_abc",
        max_seconds=240,
        poll_interval=5.0,
        sleep_fn=clock.sleep,
        now_fn=clock.now,
    )

    assert result.outcome == CallOutcome.NO_ANSWER
    assert client.deleted_rooms == ["room-2"]


async def test_sip_dial_failure_is_reported_and_room_is_cleaned_up():
    clock = FakeClock()
    client = FakeClient(active_sequence=[False])
    client.dial_error = SipDialError("trunk auth rejected")

    result = await run_call(
        client,
        scenario_slug="simple_scheduling_1",
        room_name="room-3",
        scenario_path="scenarios/simple_scheduling_1.yaml",
        phone_number="+18054398008",
        trunk_id="ST_bad",
        max_seconds=240,
        sleep_fn=clock.sleep,
        now_fn=clock.now,
    )

    assert result.outcome == CallOutcome.FAILED
    assert "trunk auth rejected" in result.error
    assert client.deleted_rooms == ["room-3"]
    assert not any(call[0] == "is_sip_participant_active" for call in client.calls)


async def test_agent_not_ready_is_reported_as_failed_and_never_dials():
    clock = FakeClock()
    client = FakeClient(active_sequence=[False], agent_ready=False)

    result = await run_call(
        client,
        scenario_slug="simple_scheduling_1",
        room_name="room-5",
        scenario_path="scenarios/simple_scheduling_1.yaml",
        phone_number="+18054398008",
        trunk_id="ST_abc",
        max_seconds=240,
        sleep_fn=clock.sleep,
        now_fn=clock.now,
    )

    assert result.outcome == CallOutcome.FAILED
    assert "agent" in result.error.lower()
    assert client.deleted_rooms == ["room-5"]
    assert not any(call[0] == "create_sip_participant" for call in client.calls)


async def test_call_exceeding_max_seconds_is_reported_as_timeout():
    clock = FakeClock()
    client = FakeClient(active_sequence=[True])

    result = await run_call(
        client,
        scenario_slug="long_call",
        room_name="room-4",
        scenario_path="scenarios/long_call.yaml",
        phone_number="+18054398008",
        trunk_id="ST_abc",
        max_seconds=10,
        poll_interval=3.0,
        sleep_fn=clock.sleep,
        now_fn=clock.now,
    )

    assert result.outcome == CallOutcome.TIMEOUT
    assert result.duration_seconds >= 10
    assert client.deleted_rooms == ["room-4"]
