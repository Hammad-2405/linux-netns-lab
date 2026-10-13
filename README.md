Linux Network Primitives

A small lab that builds a routed, firewalled virtual network on a single Linux machine using only kernel primitives: network namespaces, veth pairs, IP forwarding and nftables. I wrote it to understand how packets actually move between isolated network stacks, without Docker or any other abstraction in between.

Topology
  hostA                    router                    hostB
 ┌──────────────┐       ┌──────────────────┐       ┌──────────────┐
 │ veth_A       │◄─────►│ veth_r1  veth_r2 │◄─────►│ veth_B       │
 │ 10.0.1.2/24  │       │ 10.0.1.1 10.0.2.1│       │ 10.0.2.2/24  │
 │ nftables:    │       │ ip_forward = 1   │       │              │
 │ drop by      │       └──────────────────┘       └──────────────┘
 │ default      │
 └──────────────┘
    subnet 10.0.1.0/24                    subnet 10.0.2.0/24

Three network namespaces, each with its own interfaces, routing table and firewall:

hostA and hostB sit on two different subnets.
router connects them, with IPv4 forwarding enabled.
hostA runs a stateful nftables firewall: inbound traffic is dropped by default, except SSH (TCP 22) and replies to connections hostA started.
What it demonstrates
Namespaces as isolated network stacks: each namespace has its own interfaces, loopback, routes and firewall rules.
veth pairs as virtual cables: one end is moved into each namespace.
Routing between subnets: static routes on the hosts and net.ipv4.ip_forward on the router.
Stateful filtering with conntrack: hostA can ping out and receive replies (ct state established,related accept), while unsolicited inbound traffic is dropped and logged.
Requirements
Linux with iproute2 and nftables installed
Python 3
Root privileges, since creating namespaces and interfaces requires them
Usage
bash
sudo python3 linux_network_primitives.py

The script deletes any namespaces left from a previous run, builds the topology, applies the firewall, and pings hostB from hostA. Deleting a namespace also destroys the veth interfaces inside it.

To inspect the result:

bash
sudo ip netns exec router ip route                 # router's routing table
sudo ip netns exec hostA nft list ruleset           # hostA's firewall and drop counter
sudo ip netns exec hostB ping -c 3 10.0.1.2         # blocked by hostA's firewall

To clean up:

bash
sudo ip netns delete hostA
sudo ip netns delete router
sudo ip netns delete hostB
What I learned
<!-- Write 3–4 bullets in your own words. For example: what surprised you about conntrack, why the hosts need explicit routes, what happened before you enabled ip_forward, how you debugged a failing ping. -->
