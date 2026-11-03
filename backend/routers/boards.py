from fastapi import APIRouter, HTTPException
from storage import boards
from schemas.board import BoardCreate, BoardResponse, BoardUpdate

router = APIRouter(
    prefix="/boards",
    tags=["boards"]
)

@router.get("", response_model=list[BoardResponse])
def get_boards():
    """Zwraca wszystkie tablice"""
    return boards


@router.get("/{board_id}", response_model=BoardResponse)
def get_board(board_id: int):
    """Zwraca określoną tablicę po board_id"""
    result = next(
        (board for board in boards if board["id"] == board_id), None
    )
    
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Nie znaleziono tablicy o identyfiaktorze {}.".format(board_id)
        )
    
    return result


@router.post("", status_code=201, response_model=BoardResponse)
def create_board(board: BoardCreate):
    """Tworzy nową tablicę i nadaje jej automatyczny identyfikator."""
    new_board = {
        "id": max((item["id"] for item in boards), default=0) + 1,
        "name": board.name
    }
    boards.append(new_board)
    return new_board


@router.patch("/{board_id}", response_model=BoardResponse)
def patch_board(board_id: int, data: BoardUpdate):
    """Patchuje tablicę o wskazanym identyfikatorze."""
    board = next(
            (board for board in boards if board["id"] == board_id), None
        )

    if board is None:
        raise HTTPException(
            status_code=404,
            detail="Nie znaleziono tablicy o identyfikatorze {}".format(board_id)
        )

    changes = data.model_dump(exclude_unset = True)
    board.update(changes)

    return board


@router.delete("/{board_id}", status_code=204)
def delete_board(board_id: int):
    """Usuwa tablicę o wskazanym identyfikatorze"""
    board = next(
                (board for board in boards if board["id"] == board_id), 
                None
            )

    if board is None:
        raise HTTPException(
            status_code=404,
            detail="Nie znaleziono tablicy o identyfikatorze {}".format(board_id)
        )

    boards.remove(board)