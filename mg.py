from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
import threading
import random
import copy

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins='*')

player_lock = threading.Lock()
players = []
players_folded = set()
namemap = {}
cardmap = {}
player_limit = 8

deck_lock = threading.Lock()
game_in_progress = False
cards_left = 52
action = 0
current_bet = 0
last_action = ''
deck = [
  '2C', '2D', '2H', '2S',
  '3C', '3D', '3H', '3S',
  '4C', '4D', '4H', '4S',
  '5C', '5D', '5H', '5S',
  '6C', '6D', '6H', '6S',
  '7C', '7D', '7H', '7S',
  '8C', '8D', '8H', '8S',
  '9C', '9D', '9H', '9S',
  '10C', '10D', '10H', '10S',
  'JC', 'JD', 'JH', 'JS',
  'QC', 'QD', 'QH', 'QS',
  'KC', 'KD', 'KH', 'KS',
  'AC', 'AD', 'AH', 'AS',
]
valuemap = {
  '2' : 2,
  '3' : 3,
  '4' : 4,
  '5' : 5,
  '6' : 6,
  '7' : 7,
  '8' : 8,
  '9' : 9,
  '1' : 10,
  'J' : 11,
  'Q' : 12,
  'K' : 13,
  'A' : 14
}

@app.route('/', methods=['POST', 'GET'])
def index():
  return render_template('play.html')

def nextHand(): 
  global game_in_progress
  global cards_left 
  global current_bet
  global last_action
  global action
  global players_folded
  game_in_progress = True
  cards_left = 52
  current_bet = 0
  last_action = ''
  players_folded = set()
  for player in players:
    emit('highlight', {'name' : namemap[player], 'color' : 'white', 'border' : 'grey'}, broadcast=True)
  nextPlayer()

def showdown():
  global game_in_progress
  game_in_progress = False

  final_two = []
  for player in players:
    if player not in players_folded:
      final_two.append(player)
  if len(final_two) == 1:
    print(namemap[final_two[0]], 'wins')
  else:
    player1 = final_two[0]
    player2 = final_two[1]
    if valuemap[cardmap[player1][0]] < valuemap[cardmap[player2][0]]:
      print(namemap[player2], 'wins')
    elif valuemap[cardmap[player1][0]] > valuemap[cardmap[player2][0]]:
      print(namemap[player1], 'wins')
    else:
      print('tie')
  
def nextPlayer():
  global action
  global last_action
  action = (action + 1) % len(players)
  while players[action] in players_folded:
    action = (action + 1) % len(players)
  emit('highlight', {'name' : namemap[players[action]], 'color' : 'skyblue', 'border' : 'blue'}, broadcast=True)
  if last_action != 'fold':
    emit('highlight', {'name' : 'control_block', 'color' : 'white', 'border' : 'grey'})
  emit('highlight', {'name' : 'control_block', 'color' : 'skyblue', 'border' : 'blue'}, to=players[action])



@socketio.on('request card')
def dealCard(data):
  global cards_left
  deck_lock.acquire()
  card_index = random.randint(0, cards_left - 1)
  cards_left -= 1
  card = deck[card_index]
  deck[card_index] = deck[cards_left]
  deck[cards_left] = card
  deck_lock.release()
  cardmap[data['id']] = card
  emit('deal card', {'card' : card})


@socketio.on('init players')
def init_players():
  print(players)
  for player in players:
    emit('insert player', {'name' : namemap[player]})
  for player in players_folded:
    emit('highlight', {'name' : namemap[player], 'color' : 'lightcoral', 'border' : 'red'})
  if len(players) > 0:
    emit('highlight', {'name' : namemap[players[action]], 'color' : 'skyblue', 'border' : 'blue'})


@socketio.on('reconnection')
def reconnection(data):
  global action
  player_lock.acquire()
  for i in range(len(players)):
    if players[i] == data['old_id']:
      players[i] = data['new_id']
      break
  player_lock.release()
  namemap[data['new_id']] = namemap[data['old_id']]
  namemap.pop(data['old_id'])
  cardmap[data['new_id']] = cardmap[data['old_id']]
  cardmap.pop(data['old_id'])
  if data['old_id'] in players_folded:
    players_folded.remove(data['old_id'])
    players_folded.add(data['new_id'])
    emit('highlight', {'name' : 'control_block', 'color' : 'lightcoral', 'border' : 'red'})
  if i == action:
    emit('highlight', {'name' : 'control_block', 'color' : 'skyblue', 'border' : 'blue'})
  emit('deal card', {'card' : cardmap[data['new_id']]})


@socketio.on('play')
def sit(data):
  print('sit')
  global game_in_progress
  if data['id'] not in players and data['name'] != '' and len(players) < player_limit:
    player_lock.acquire()
    players.append(data['id'])
    player_lock.release()
    namemap[data['id']] = data['name']
    cardmap[data['id']] = 'Red_back'
    emit('insert player', {'name' : data['name']}, broadcast=True)
    emit('successful join', {'name' : data['name']})
    if len(players) == 1:
      emit('highlight', {'name' : namemap[players[0]], 'color' : 'skyblue', 'border' :'blue'}, broadcast=True)
      emit('highlight', {'name' : 'control_block', 'color' : 'skyblue', 'border' :'blue'}, to=players[0])
    if game_in_progress:
      emit('highlight', {'name' : namemap[data['id']], 'color' : 'lightcoral', 'border' : 'red'}, broadcast=True)
      emit('highlight', {'name' : 'control_block', 'color' : 'lightcoral', 'border' :'red'})
      players_folded.add(data['id'])

  elif data['id'] in players and players[action] == data['id']:
    nextHand()
    emit('highlight', {'name' : namemap[players[action]], 'color' : 'skyblue', 'border' : 'blue'}, broadcast=True)
    emit('start game', to='private room')


@socketio.on('leave game')
def leave(data):
  print('leave')
  global game_in_progress
  global action
  val = namemap[data['id']]
  if data['id'] in players and game_in_progress:
    emit('warning', {'val' : 'CANNOT LEAVE DURING A HAND'})
  elif data['id'] in players and not game_in_progress:
    player_lock.acquire()
    index = 0
    for i in range(len(players)):
      if players[i] == data['id']:
        index = i
    players.remove(data['id'])
    namemap.pop(data['id'])
    player_lock.release()
    if index <= action and len(players) > 0:
      action = (action - 1) % len(players) 
      emit('highlight', {'name' : namemap[players[action]], 'color' : 'skyblue', 'border' : 'blue'}, broadcast=True)
      emit('highlight', {'name' : 'control_block', 'color' : 'skyblue', 'border' : 'blue'}, to=players[action])

    emit('highlight', {'name' : 'control_block', 'color' : 'white', 'border' : 'grey'})
    emit('delete player', {'name' : val}, broadcast=True)
    emit('successful leave')


# fold call raise
@socketio.on('fold')
def fold(data):
  global action
  global last_action
  if players[action] != data['id']:
    emit('warning', {'val' : 'OUT OF TURN'})
  elif not game_in_progress:
    emit('warning', {'val' : 'GAME HASNT BEEN STARTED'})
  else:
    players_folded.add(data['id'])
    if len(players) - len(players_folded) == 2 and last_action == 'call':
      showdown()
    elif len(players) - len(players_folded) == 1:
      showdown()
    else:
      emit('highlight', {'name' : namemap[players[action]], 'color' : 'lightcoral', 'border' : 'red'}, broadcast=True)
      emit('highlight', {'name' : 'control_block', 'color' : 'lightcoral', 'border' : 'red'})
      last_action = 'fold'
      nextPlayer()


@socketio.on('call')
def call(data):
  global action
  global last_action
  global current_bet
  if players[action] != data['id']:
    emit('warning', {'val' : 'OUT OF TURN'})
  elif not game_in_progress:
    emit('warning', {'val' : 'GAME HASNT BEEN STARTED'})
  elif last_action == 'call':
    emit('warning', {'val' : 'ONLY ONE CALL IS ALLOWED'})
  elif not current_bet:
    emit('warning', {'val' : 'NO BET TO CALL'})
  else:
    if len(players) - len(players_folded) == 2:
      showdown()
    else:
      emit('highlight', {'name' : namemap[players[action]], 'color' : 'white', 'border' : 'grey'}, broadcast=True)
      nextPlayer()
      last_action = 'call'
  

@socketio.on('raise') # make this a raise / bet event
def raisebet(data):
  global action
  global last_action
  global current_bet
  if players[action] != data['id']:
    emit('warning', {'val' : 'OUT OF TURN'})
  elif not game_in_progress:
    emit('warning', {'val' : 'GAME HASNT BEEN STARTED'})
  elif not data['val'].isnumeric():
    emit('warning', {'val' : 'INVALID RAISE'})
  elif int(data['val']) < current_bet:
    emit('warning', {'val' : 'RAISE/BET TOO LOW'})
  elif int(data['val']) > int(data['stack']):
    emit('warning', {'val' : 'NOT ENOUGH MONEY'})
  else:
    current_bet = int(data['val'])
    emit('highlight', {'name' : namemap[players[action]], 'color' : 'white', 'border' : 'grey'}, broadcast=True)
    nextPlayer()
    emit('update', {'id' : 'pot', 'val' : data['val']}, broadcast=True)
    last_action = 'raise'


# handle joining and leaving rooms
@socketio.on('join')
def join(data):
    join_room(data['room'])

@socketio.on('leave')
def leave(data):
    leave_room(data['room'])


if __name__ == '__main__':
  socketio.run(app)#, host='0.0.0.0')