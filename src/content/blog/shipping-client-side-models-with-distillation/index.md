---
title: "Video Game Development: Shipping Client Side Models with Distillation"
date: 2026-11-19
---
## The Problem with Gaming and Artificial Intelligence

In the last 6-12 months, everyone even tangentially involved with gaming has had to true up their beliefs in regards to the role that AI plays in making and playing video games. Factions have formed and the mob is out for anything that has the AI label. I understand and appreciate some of the anti-AI argument when it comes to art, creativity, and the preservation of the human craft. I unequivocally support the role of humans in art and craft. 

With that said, I actually want to tackle a separate question related to AI in games. If we now have this explosion of machine intelligence, what will it take to make game AI feel organic as well. Theoretically, AI systems that drive in-game agents should look and play better.

### Building Inuition for Using AI in the Game Loop

Why would you even want to use LLMs in the game loop?

I often run into people who are earnestly curious about what this new technology can do for them, and they are usually eager to implement it in whatever way is natural. Think the chatbot explosion on every B2B SaaS product from 2023-2025. Unfortunately, most of these applications were useless and simply not fun. So my angle here takes more lessons from the agentic era than the chatbot era.

For the uninitiated, the agentic era was when we all realized that LLMs were not just great chatbots, but we could also teach them how to speak in tool uses. Meaning that they could meaningfully effect the world outside their chat thread. With the advent of reasoning models, tool use became something absurdly powerful. We now have blender agents that can do entire modelling flows faster than you can have a meal. 

So the way to think about tool use and reasoning with respect to video game intelligence, is to think about it in a generic reinforecment learning lens. Each of these agentic workflows is an episode with a particular trajectory that is suppoosed to achieve some goal. Because the combination of tool use and reasoning so potent, building in agentic flows to in-game AI systems is appealing.

The thought that comes to my head when working on my own projects is building systems that take soft, hard to define features (such as the level of excitement about an upcoming game in a sports simulation) and output incredibly immersive flavor into the game loop. If we can have access to systems that inuitively know what these soft features approximately should be, we can define trajectories that trigger tools to fit the true flavor like a glove.

### Enumerating the Problems with Using Artificial Intelligence in the Game Loop

Quickly, we should talk about the reasons why its challenging to offload their intelligence in in-game AI systems.

**Size** - the best open source model currently available is Kimi K3.1 Pro at 2.8T parameters, weighing 1.56 TB. Simply a non starter to ship client side, meaning that as a developer you would be making API calls and deciding if and how you would want to cover costs of serving such a model.

**Speed** - modern LLMs keeping growing in size to chase intelligence with scaling laws. That means, barring large leaps in algoritmic efficiency, the models will only take longer to yield results you and I expect. This means, as a developer, you can't expect timely results even before accounting for network errors.

**Cost** - incremental costs for playing a game are deeply unappealing to both developers and customers. Developers are fronting lots of effort and investment, and to have the potential payoff be whittled down would be a disappointing outcome. On the other hand, players are usually unwilling to be taxed or play games on a subscription model (unless they are truly transcedent in a particular niche, i.e. iRacing).

So, if you wanted to use this next generation of intelligence, you are fairly handcuffed with ugly problems to solve.

### A Generic Example: Defining a Flavor System

In this case, we have a system who's job it is to immerse the player with flavor text that shoulders some portion of what I'll informally call autonomous world building. I'll run with the aforementioned game excitement example, and in this case it should help generate a pre-game news article for the player to skim before a match.

**Potential Inputs**
- Inputs from the game environemnt
- User inputs

**Outputs**
- Intermediary outcomes that describe the world at compute-time
- Scored outcomes
- Flavor Text built from the above

**Goals**

1. Minimize costs at runtime
2. Maximize narrative customization
3. Maximize variety of results
4. Minimize confusing resutls

