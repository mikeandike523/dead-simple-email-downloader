# AGENTS.md

Facts about the development environment

## Packages and building

You are an agent running out of wsl, but all runtimes and package managers are on the windows host machine.
This inevitably makes things tricky.

Some runtimes and package managers are supported in part in your environment, but not all. Therefore:

    You can modify package.json and requirements.txt files

    you can attempt pnpm install but it may not always work

    For python, I recommend using "bash __inenv ..."
    to get a reliable python or pip executable for installing packages and checking syntax

    You can attempt pnpm run lint and pnpm run build as an easy way to typecheck but it may not work
    You can run "tsc", which will call the globally installed typescript cli

## Your main goal
Your main goal is to be like a super-smart autocomplete, writing blocks of code and making code changes that a human will review
Essentially, you are writing code that the programmer would have written themselves anyway, if given more time
This means you should try to use existing code as stylistic and structure guides

## Caution and Fastidiousness
Please do not hesitate to ask questions if you need to know something
It's better to do things right even if it takes longer to develop

## Communication Skills
In your summaries of your actions, make sure to point out what code needs to be tested and verified,
including which code you could or could not verify yourself

## Tests
At this time, we do not have any corpus of mock data that would support unit testing
So no tests at this time
This is a small project meant to solve a niche IT issue 