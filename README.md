# The Termailnator

This project is to summarize the high load of emails I get every day, and does it almost all by itself, completely 
automated.

## Current Functionality
- Sends a summary at 10am every day automatically
- also produces summaries on demand if I email the fmail account with subject line "Sum"

## Future Ambition
- Expand the pub/sub trigger to allow for custom parameters when summarizing, like timeframe and prompt add-ons
- Experiment with automated responses for things other than summaries
- Maybe even connect this to twilio API to call me when an important email hits

## Notes
This project is an unpublished google cloud project, and having never used google cloud before I used this as an 
opportunity to explore this unique but useful service. As this was a somewhat new domain, I had a lot of help from
google's own documentation, and claude (just chat, not code) on how to interact with these APIs. Also, this purely a 
personal project with no other motivation but my laziness and a want to learn a new cloud platform.