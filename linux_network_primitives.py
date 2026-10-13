import os
import subprocess
import sys

def run_cmd(cmd):
    print("running command " + " ".join(cmd))
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        print(result.stderr.strip())
        sys.exit(1)
    if result.stdout:
        print(result.stdout.strip())

def main():
    #namespaces and interfaces can only be created as root
    if os.geteuid() != 0:
        print("this script must be run as root: sudo python3 linux_network_primitives.py")
        sys.exit(1)

    #deleting existing namespaces from previous run
    print("--- cleaning up old namespaces ---")
    subprocess.run(["ip", "netns", "delete", "hostA"], stderr=subprocess.DEVNULL)
    subprocess.run(["ip", "netns", "delete", "router"], stderr=subprocess.DEVNULL)
    subprocess.run(["ip", "netns", "delete", "hostB"], stderr=subprocess.DEVNULL)

    #creating new namespaces
    print("\n--- creating namespaces ---")
    run_cmd(["ip", "netns", "add", "hostA"])
    run_cmd(["ip", "netns", "add", "router"])
    run_cmd(["ip", "netns", "add", "hostB"])

    subprocess.run(["ip", "netns", "exec", "hostA", "nft", "flush", "ruleset"], stderr=subprocess.DEVNULL)

    #creating veth pairs
    print("\n--- creating veth pairs ---")
    run_cmd(["ip", "link", "add", "veth_A", "type", "veth", "peer", "name", "veth_r1"])
    run_cmd(["ip", "link", "add", "veth_B", "type", "veth", "peer", "name", "veth_r2"])

    #assinging each veth end to its namespaces
    print("\n--- moving Interfaces into namespaces ---")
    run_cmd(["ip", "link", "set", "veth_A", "netns", "hostA"])
    run_cmd(["ip", "link", "set", "veth_r1", "netns", "router"])
    run_cmd(["ip", "link", "set", "veth_r2", "netns", "router"])
    run_cmd(["ip", "link", "set", "veth_B", "netns", "hostB"])

    #bringing up veth and loopback interfaces inside namespaces
    print("\n--- Bringing up Interfaces ---")
    run_cmd(["ip", "netns", "exec", "hostA", "ip", "link", "set", "veth_A", "up"])
    run_cmd(["ip", "netns", "exec", "hostA", "ip", "link", "set", "lo", "up"])
    run_cmd(["ip", "netns", "exec", "router", "ip", "link", "set", "veth_r1", "up"])
    run_cmd(["ip", "netns", "exec", "router", "ip", "link", "set", "veth_r2", "up"])
    run_cmd(["ip", "netns", "exec", "router", "ip", "link", "set", "lo", "up"])
    run_cmd(["ip", "netns", "exec", "hostB", "ip", "link", "set", "veth_B", "up"])
    run_cmd(["ip", "netns", "exec", "hostB", "ip", "link", "set", "lo", "up"])

    #enable ip forwarding
    print("\n--- Enable ip forwarding ---")
    run_cmd(["ip", "netns", "exec", "router", "sysctl", "-w", "net.ipv4.ip_forward=1"])

    #assinging ip addresses
    print("\n--- Assigning IP Addresses ---")
    run_cmd(["ip", "netns", "exec", "hostA", "ip", "addr", "add", "10.0.1.2/24", "dev", "veth_A"])
    run_cmd(["ip", "netns", "exec", "router", "ip", "addr", "add", "10.0.1.1/24", "dev", "veth_r1"])
    run_cmd(["ip", "netns", "exec", "router", "ip", "addr", "add", "10.0.2.1/24", "dev", "veth_r2"])
    run_cmd(["ip", "netns", "exec", "hostB", "ip", "addr", "add", "10.0.2.2/24", "dev", "veth_B"])

    #adding routes
    print("\n--- Adding Routes ---")
    run_cmd(["ip", "netns", "exec", "hostA", "ip", "route", "add", "10.0.2.0/24", "via", "10.0.1.1"])
    run_cmd(["ip", "netns", "exec", "hostB", "ip", "route", "add", "10.0.1.0/24", "via", "10.0.2.1"])

    #adding firewall rules on hostA
    print("\n--- Applying Firewall Rules on hostA ---")
    run_cmd(["ip", "netns", "exec", "hostA", "nft", "add", "table", "inet", "filter"])
    run_cmd(["ip", "netns", "exec", "hostA", "nft", "add", "chain", "inet", "filter", "input",
              "{ type filter hook input priority 0 ; policy drop ; }"])
    #allow hostA's own loopback traffic before anything else is filtered
    run_cmd(["ip", "netns", "exec", "hostA", "nft", "add", "rule", "inet", "filter", "input",
              "iif", "lo", "accept"])
    run_cmd(["ip", "netns", "exec", "hostA", "nft", "add", "rule", "inet", "filter", "input",
              "tcp", "dport", "22", "accept"])
    run_cmd(["ip", "netns", "exec", "hostA", "nft", "add", "rule", "inet", "filter", "input",
              "ct", "state", "established,related", "accept"])
    run_cmd(["ip", "netns", "exec", "hostA", "nft", "add", "rule", "inet", "filter", "input",
              "counter", "log", "prefix", "\"dropped: \"", "drop"])

    #testing: routing works, hostA can reach hostB and gets replies back
    print("\n--- Test 1: hostA -> hostB (should succeed) ---")
    run_cmd(["ip", "netns", "exec", "hostA", "ping", "-c", "3", "10.0.2.2"])

    #testing: unsolicited traffic into hostA is dropped by the firewall
    print("\n--- Test 2: hostB -> hostA (should be blocked by hostA's firewall) ---")
    result = subprocess.run(["ip", "netns", "exec", "hostB", "ping", "-c", "3", "-W", "1", "10.0.1.2"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0:
        print("FAIL: hostB reached hostA, the firewall is not blocking inbound traffic")
        sys.exit(1)
    print("PASS: hostB's pings to hostA were dropped")

    #showing the ruleset, the drop counter should now be above zero
    print("\n--- hostA ruleset and drop counter ---")
    run_cmd(["ip", "netns", "exec", "hostA", "nft", "list", "ruleset"])


if __name__ == "__main__":
    main()
