from typing import cast as typing_cast

cast = typing_cast
"""### Midas documentation
Cast a value to a type.

- **Compile-time**: tells the type checker that the return value has the designated type.
- **Run-time**: generates assertions to ensure the value can be interpreted as the given type.

---
<br>
<br>
<br>

_**Internal Python documentation**_
"""


unsafe_cast = typing_cast
"""### Midas documentation
Cast a value to a type.

- **Compile-time**: tells the type checker that the return value has the designated type.
- **Run-time**: -

This operation is unsound, use at your own risk!

---
<br>
<br>
<br>

_**Internal Python documentation**_
"""
