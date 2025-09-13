Small stuff
1) Replace logging from JSON to MongoDB
2) Decide bw mock api & real api
3) Rate limits
4) Figure out alerts - Is data validation & Recon different?
5) Admin key for prod in api/deps
6) Generate API keys for affiliates
7) Get hidden insights, Affiliate platform API keys
8) docker
9) Platforms can have different links when share button is click, how to point them to 1 post in backend?
10) circuit breaker for external platforms

Major reqs
Platform APIs
Reconcillioation
Data cleaning 
 - Missing data, duplicates or discripencies
 - 2 is not a problem, reconcilliation handles 3, for missing data we can alert if a post has not been updated in a while (we might be behind on views)