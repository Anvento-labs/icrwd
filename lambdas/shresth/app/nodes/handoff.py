def handoff_node(state):
    print("---HANDOFF TRIGGERED---")
    msg = "I've flagged your conversation for a human agent. Someone will review your case immediately."
    return {
        "generation": msg
    }