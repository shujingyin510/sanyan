import threading
import random
import time
import logging
from enum import Enum


class Role(Enum):
    """Possible roles of a Raft node."""
    FOLLOWER = 0
    CANDIDATE = 1
    LEADER = 2


class LogEntry:
    """A single entry in the Raft log.

    Attributes:
        term: The term in which the entry was created.
        command: The command to be applied to the state machine.
    """

    def __init__(self, term: int, command: str) -> None:
        self.term = term
        self.command = command

    def to_dict(self) -> dict:
        """Serialize the entry to a dictionary."""
        return {'term': self.term, 'command': self.command}

    @classmethod
    def from_dict(cls, data: dict) -> 'LogEntry':
        """Create a LogEntry from a dictionary."""
        return cls(data['term'], data['command'])


class RaftNode:
    """A node implementing the Raft consensus protocol.

    Attributes:
        node_id: Unique identifier for this node.
        peers: List of other node IDs.
        state: Current role of the node.
        currentTerm: Latest term server has seen.
        votedFor: CandidateId that received vote in current term.
        log: List of log entries.
        commitIndex: Index of highest log entry known to be committed.
        lastApplied: Index of highest log entry applied to state machine.
        nextIndex: For each server, index of the next log entry to send.
        matchIndex: For each server, index of highest log entry known to be replicated.
        leaderId: Id of current leader (if known).
        election_timeout_min/max: Milliseconds for election timeout range.
        heartbeat_interval: Milliseconds between heartbeats.
    """

    def __init__(self, node_id: str, peers: list,
                 election_timeout_min: int = 150,
                 election_timeout_max: int = 300,
                 heartbeat_interval: int = 50) -> None:
        self.node_id = node_id
        self.peers = peers
        self.state = Role.FOLLOWER
        self.currentTerm = 0
        self.votedFor = None
        self.log: list[LogEntry] = []
        self.commitIndex = 0
        self.lastApplied = 0
        self.nextIndex = {peer: 1 for peer in peers}
        self.matchIndex = {peer: 0 for peer in peers}
        self.leaderId = None
        self.election_timeout_min = election_timeout_min
        self.election_timeout_max = election_timeout_max
        self.heartbeat_interval = heartbeat_interval
        self.election_timer: threading.Timer | None = None
        self.heartbeat_timer: threading.Timer | None = None
        self.lock = threading.RLock()
        self.apply_channel: list[LogEntry] = []
        self.shutdown = False
        self.network = None  # will be set by the network
        self.logger = logging.getLogger(f"Node-{node_id}")
        self.reset_election_timer()

    def reset_election_timer(self) -> None:
        """Reset the election timer with a random timeout."""
        if self.election_timer:
            self.election_timer.cancel()
        timeout = random.uniform(self.election_timeout_min,
                                 self.election_timeout_max) / 1000.0
        self.election_timer = threading.Timer(timeout, self.start_election)
        self.election_timer.daemon = True
        self.election_timer.start()

    def start_election(self) -> None:
        """Begin an election, requesting votes from peers."""
        with self.lock:
            if self.state == Role.LEADER:
                return
            self.state = Role.CANDIDATE
            self.currentTerm += 1
            self.votedFor = self.node_id
            self.logger.info("Starting election for term %d", self.currentTerm)

            last_log_index = len(self.log)
            last_log_term = self.log[-1].term if self.log else 0
            request = {
                'term': self.currentTerm,
                'candidateId': self.node_id,
                'lastLogIndex': last_log_index,
                'lastLogTerm': last_log_term
            }
            votes = 1  # vote for self
            for peer in self.peers:
                response = self.send_rpc(peer, 'RequestVote', request)
                if response:
                    if response['term'] > self.currentTerm:
                        self.become_follower(response['term'])
                        return
                    if response['voteGranted']:
                        votes += 1
                        if votes > (len(self.peers) + 1) // 2:
                            self.become_leader()
                            return