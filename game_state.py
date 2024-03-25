from enum import Enum
from copy import deepcopy
import numpy as np

class GameState:
    board_width = None
    board_height = None
    food_locations = None
    minimum_food = None
    hazard_locations = None
    hazard_damage = None
    enemy_snake = None
    player_snake = None
    turn = None

    class Move(Enum):
        UP = 1
        DOWN = 2
        LEFT = 3
        RIGHT = 4

    def __init__(self, game_state_json):
        self.board_width = game_state_json["board"]["width"]
        self.board_height = game_state_json["board"]["height"]
        self.food_locations = game_state_json["board"]["food"]
        self.hazard_locations = game_state_json["board"]["hazards"]
        self.hazard_damage = game_state_json["game"]["ruleset"]["settings"]["hazardDamagePerTurn"]
        self.player_snake = Snake(game_state_json["you"])

        # This previously relied on sorting order, I don't think my assumptions were correct, so now we search the whole json for the snake that isn't us
        for snake in game_state_json["board"]["snakes"]:
            enemy_snake = Snake(snake)
            if (enemy_snake != self.player_snake):
                self.enemy_snake = enemy_snake
                break

        self.turn = game_state_json["turn"]
        

    def apply_move_player(self, move_option):
        if (move_option == self.Move.UP):
            self.player_snake.head = {"x": self.player_snake.head["x"], "y": self.player_snake.head["y"] + 1}
            self.player_snake.body.insert(0, self.player_snake.head)
        
        if (move_option == self.Move.DOWN):
            self.player_snake.head = {"x": self.player_snake.head["x"], "y": self.player_snake.head["y"] - 1}
            self.player_snake.body.insert(0, self.player_snake.head)

        if (move_option == self.Move.LEFT):
            self.player_snake.head = {"x": self.player_snake.head["x"] - 1, "y": self.player_snake.head["y"]}
            self.player_snake.body.insert(0, self.player_snake.head)
        
        if (move_option == self.Move.RIGHT):
            self.player_snake.head = {"x": self.player_snake.head["x"] + 1, "y": self.player_snake.head["y"]}
            self.player_snake.body.insert(0, self.player_snake.head)

        if(self.did_obtain_food(self.player_snake)):
            self.player_snake.length = self.player_snake.length + 1
            self.player_snake.health = 100
        else:
            self.player_snake.health = self.player_snake.health - 1
            del self.player_snake.body[-1]


    def apply_move_enemy(self, move_option):
        if (move_option == self.Move.UP):
            self.enemy_snake.head = {"x": self.enemy_snake.head["x"], "y": self.enemy_snake.head["y"] + 1}
            self.enemy_snake.body.append(self.enemy_snake.head)
        
        if (move_option == self.Move.DOWN):
            self.enemy_snake.head = {"x": self.enemy_snake.head["x"], "y": self.enemy_snake.head["y"] - 1}
            self.enemy_snake.body.append(self.enemy_snake.head)

        if (move_option == self.Move.LEFT):
            self.enemy_snake.head = {"x": self.enemy_snake.head["x"] - 1, "y": self.enemy_snake.head["y"]}
            self.enemy_snake.body.append(self.enemy_snake.head)
        
        if (move_option == self.Move.RIGHT):
            self.enemy_snake.head = {"x": self.enemy_snake.head["x"] + 1, "y": self.enemy_snake.head["y"]}
            self.enemy_snake.body.append(self.enemy_snake.head)

        # Did_obtain_food will remove the food from the game state within the function
        if(self.did_obtain_food(self.enemy_snake)):
            self.enemy_snake.length = self.enemy_snake.length + 1
            self.enemy_snake.health = 100
        else:
            self.enemy_snake.health = self.enemy_snake.health - 1
            del self.enemy_snake.body[-1]


    def did_obtain_food(self, snake):
        for food in self.food_locations:
            if (snake.head["x"] == food["x"] and snake.head["y"] == food["y"]):
                self.food_locations.remove(food)
                return True
        return False


    def state_score(self):
        # This function assumes that an apply_move has been done, however, it should be valid regardless
        # I have hardcoded any guaranteed fail states as a -infinity for the player
        # The checks are done in order of least expensive check to most expensive
        if (self.player_snake.head["y"] < 0):
            return -np.Infinity

        if (self.player_snake.head["x"] < 0):
            return -np.Infinity
        

        if (self.player_snake.head["y"] > self.board_height - 1):
            return -np.Infinity
        
        if (self.player_snake.head["x"] > self.board_width - 1):
            return -np.Infinity

        # If the player's new head position would be in the body of our snake
        # does not consider body[0] because it is the old/new head's position
        # we don't ignore body[1] because while it could theoretically be a head position
        # a move hasn't necesarrily been applied
        if (self.player_snake.head in self.player_snake.body[1:]):
            return -np.Infinity
        
        # If the player's new head position would be in the body of another snake
        if (self.player_snake.head in self.enemy_snake.body[1:]):
            return -np.Infinity

        # This check would be if we collide with an enemy snake's head and our length is less than or equal to theirs
        # for now I consider a draw just as bad as a loss
        if (self.player_snake.head == self.enemy_snake.head and self.player_snake.length <= self.enemy_snake.length):
            return -np.Infinity
        elif (self.player_snake.head == self.enemy_snake.head and self.player_snake.length > self.enemy_snake.length):
            return np.Infinity

        # Actual heuristics begin below here
        base_score = 0

        # Health scaling factor for food importance
        health_scaling_factor = 1 - (self.player_snake.health / 100)  # More importance as health decreases

        # Finding the closest food distance
        closest_food_distance = np.Infinity
        for food in self.food_locations:
            dist = abs(self.player_snake.head["x"] - food["x"]) + abs(self.player_snake.head["y"] - food["y"])
            if dist < closest_food_distance:
                closest_food_distance = dist
    
        # Food score contribution, adjusted by health scaling factor
        if closest_food_distance < np.Infinity:
            base_score += ((self.board_height + self.board_width) / closest_food_distance) * health_scaling_factor

        # Proximity to hazards calculation
        min_distance_to_hazard = np.Infinity
        if self.hazard_locations:
            for hazard in self.hazard_locations:
                dist_to_hazard = abs(self.player_snake.head["x"] - hazard["x"]) + abs(self.player_snake.head["y"] - hazard["y"])
                if dist_to_hazard < min_distance_to_hazard:
                    min_distance_to_hazard = dist_to_hazard
        # Penalize based on proximity to the nearest hazard
        if min_distance_to_hazard < np.Infinity:
            hazard_proximity_penalty = -100 / (1 + min_distance_to_hazard)  # Strong penalty for being close to hazards
            base_score += hazard_proximity_penalty

        # Aggressiveness towards enemy snake when our snake is longer
        if self.player_snake.length > self.enemy_snake.length:
            dist_to_enemy_head = abs(self.player_snake.head["x"] - self.enemy_snake.head["x"]) + abs(self.player_snake.head["y"] - self.enemy_snake.head["y"])
            aggressiveness_score = 10 / (1 + dist_to_enemy_head)  # Encourage getting closer when longer
            base_score += aggressiveness_score

        # Return the final score
        return base_score

class Snake:
    id: None
    health: None
    length: None
    head: None
    body: None


    def __init__(self, snake_json):
        self.id = snake_json["id"]
        self.health = snake_json["health"]
        self.length = snake_json["length"]
        self.head = snake_json["head"]
        self.body = snake_json["body"]


def minimax(game_state, depth, maximizing_player):
    # TODO: Determine what gameState is terminal means?
    if (depth == 0 or game_state.state_score() == -np.Infinity or game_state.state_score() == np.Infinity and game_state.turn != 0):
        return [game_state.state_score(), None]
        
    if (maximizing_player):
        bestScore = -np.Infinity
        bestMove = None
        for move_option in GameState.Move:
            newState = deepcopy(game_state)
            newState.apply_move_player(move_option)
            newStateScore, _ = minimax(newState, depth - 1, False)
            if newStateScore > bestScore:
                print("Choosing new move (max): {}, {}".format(move_option, newStateScore))
                bestScore = newStateScore
                bestMove = move_option
        return [bestScore, bestMove]
    else:
        bestScore = np.Infinity
        bestMove = None
        for move_option in GameState.Move:
            newState = deepcopy(game_state)
            newState.apply_move_enemy(move_option)
            newStateScore, _ = minimax(newState, depth - 1, True)
            if newStateScore < bestScore:
                print("Choosing new move (min): {}, {}".format(move_option, newStateScore))
                bestScore = newStateScore
                bestMove = move_option
        return [bestScore, bestMove]